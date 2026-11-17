"""Read-only bounded Linux procfs and log-metadata observations, never liveness.

identity = pin_owned_process(pid, process_group_id)
observer = ProcessObserver(identity, log_paths=[external_log])
observer.sample()  # caller polls; None until >=2 seconds, no sleep/thread/launch
report = observer.report()  # detached JSON data; caller owns persistence

Caller asserts ownership using an explicitly supplied PID/group, checked against
kernel start ticks/group before AND after counter reads. No PID discovery,
command/environment reading, signals, subprocesses, game calls or file writes.
One PID only: wrapper counters do not represent its server descendants. Missing
data is unavailable, never zero. All snapshots are best-effort, not atomic.
CPU/I/O/log growth cannot establish engine progress, readiness or a deadlock.
Finite IO/count/byte work cannot preempt an OS/filesystem stall: caller retains
its external monotonic deadline and cleanup. Windows process data is explicitly
unavailable; Linux procfs input roots and clocks can be injected for tests.
"""
import copy
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

INTERVAL_SECONDS=2
MAX_SAMPLES=512
MAX_REPORT_BYTES=2*1024*1024
STOP_REPORT_RESERVE_BYTES=256
MAX_PROC_BYTES=64*1024
MAX_LOGS=8


class _InputError(ValueError):
    pass


def _integer(value,low=0,high=(1<<64)-1):
    if type(value) is not int or not low<=value<=high: raise ValueError('integer outside bounds')
    return value


def _platform(value):
    value=sys.platform if value is None else value
    if type(value) is not str or not 1<=len(value)<=32 or not value.isascii():
        raise ValueError('bounded platform identifier required')
    return value


def _path(value):
    result=Path(value)
    if '..' in result.parts: raise ValueError('parent traversal forbidden')
    result=result.absolute()
    if len(str(result).encode())>512: raise ValueError('path length budget exceeded')
    return result


def _checked_stat(path):
    for node in (path,*path.parents):
        info=os.lstat(node)
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&1024:
            raise _InputError('unsafe_path')
    info=os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1: raise _InputError('unsafe_file')
    return info


def _read(path,limit):
    """procfs reports st_size=0; bound actual bytes rather than trusting size."""
    info=_checked_stat(path)
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_CLOEXEC',0)
    descriptor=os.open(path,flags)
    with os.fdopen(descriptor,'rb') as stream:
        opened=os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink!=1 or (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):
            raise _InputError('input_changed')
        data=stream.read(limit+1)
    if len(data)>limit: raise _InputError('input_byte_budget')
    return data


def _reason(exc):
    if isinstance(exc,_InputError): return str(exc)[:64]
    if isinstance(exc,PermissionError): return 'permission_denied'
    if isinstance(exc,FileNotFoundError): return 'missing'
    if isinstance(exc,OSError): return 'os_error_'+str(exc.errno)
    return 'malformed'


def _unsigned(token):
    if not re.fullmatch(rb'[0-9]{1,20}',token): raise _InputError('malformed')
    return _integer(int(token))


def _stat(data,pid):
    # comm may contain spaces and parentheses. Fields start AFTER its final ')'.
    opening=data.find(b'('); closing=data.rfind(b')')
    if opening<1 or closing<opening or _unsigned(data[:opening].strip())!=pid:
        raise _InputError('malformed')
    fields=data[closing+1:].split()
    if len(fields)<22 or len(fields)>128 or not re.fullmatch(rb'[A-Za-z]',fields[0]):
        raise _InputError('malformed')
    return dict(pid=pid,state=fields[0].decode('ascii'),process_group_id=_unsigned(fields[2]),
        utime_ticks=_unsigned(fields[11]),stime_ticks=_unsigned(fields[12]),
        threads=_unsigned(fields[17]),starttime_ticks=_unsigned(fields[19]),
        virtual_bytes=_unsigned(fields[20]),rss_pages=_unsigned(fields[21]))


def _same(observed,identity):
    if observed['starttime_ticks']!=identity['starttime_ticks']: return 'pid_reused'
    if observed['process_group_id']!=identity['process_group_id']: return 'process_group_changed'
    return None


def pin_owned_process(pid,process_group_id,*,proc_root='/proc',platform=None):
    """Ownership is asserted by caller; membership/start time are observed here."""
    _integer(pid,1,(1<<31)-1); _integer(process_group_id,1,(1<<31)-1)
    root=_path(proc_root); platform=_platform(platform)
    result=dict(pid=pid,process_group_id=process_group_id,starttime_ticks=None,
        status='unavailable',reason=None,platform=platform)
    if platform!='linux': result['reason']='unsupported_platform'; return result
    try:
        first=_stat(_read(root/str(pid)/'stat',MAX_PROC_BYTES),pid)
        if first['process_group_id']!=process_group_id:
            result.update(status='rejected',reason='process_group_changed'); return result
        second=_stat(_read(root/str(pid)/'stat',MAX_PROC_BYTES),pid)
        if _same(second,first): result.update(status='rejected',reason='identity_changed_while_pinning'); return result
        result.update(status='available',reason=None,starttime_ticks=first['starttime_ticks'])
    except (OSError,ValueError) as exc: result['reason']=_reason(exc)
    return result


def _fields(data,names,*,kilobytes=False):
    lines=data.splitlines()
    if len(lines)>256: raise _InputError('field_count_budget')
    values={name:None for name in names}; errors={}; seen=set()
    for line in lines:
        key,separator,raw=line.partition(b':')
        if not separator or key not in names: continue
        if key in seen: values[key]=None; errors[key]='duplicate'; continue
        seen.add(key)
        try:
            parts=raw.split()
            if kilobytes and key!=b'Threads':
                if len(parts)!=2 or parts[1]!=b'kB': raise _InputError('malformed')
                value=_unsigned(parts[0])*1024
            else:
                if len(parts)!=1: raise _InputError('malformed')
                value=_unsigned(parts[0])
            values[key]=value
        except ValueError: errors[key]='malformed'
    for key in names:
        if key not in seen: errors[key]='missing'
    return values,errors


def encode_report(report):
    return (json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


class ProcessObserver:
    def __init__(self,identity,*,log_paths=(),proc_root='/proc',platform=None,clock=None,
                 max_samples=MAX_SAMPLES,max_bytes=MAX_REPORT_BYTES,clock_ticks=None,page_size=None):
        _integer(max_samples,1,MAX_SAMPLES); _integer(max_bytes,2048,MAX_REPORT_BYTES)
        if type(identity) is not dict: raise ValueError('pinned identity required')
        self.identity={key:identity.get(key) for key in ('pid','process_group_id','starttime_ticks','status','reason','platform')}
        _integer(self.identity['pid'],1,(1<<31)-1); _integer(self.identity['process_group_id'],1,(1<<31)-1)
        if self.identity['status'] not in ('available','unavailable','rejected'):
            raise ValueError('explicit pin outcome required')
        _platform(self.identity['platform'])
        reason=self.identity['reason']
        if reason is not None and (type(reason) is not str or not 1<=len(reason)<=96):
            raise ValueError('bounded explicit identity reason required')
        if self.identity['status']!='available' and reason is None:
            raise ValueError('unavailable identity requires reason')
        ticks=self.identity['starttime_ticks']
        if ticks is not None or self.identity['status']=='available': _integer(ticks)
        if type(log_paths) not in (tuple,list) or len(log_paths)>MAX_LOGS: raise ValueError('bounded explicit log list required')
        self.paths=tuple(_path(p) for p in log_paths)
        if len(set(self.paths))!=len(self.paths): raise ValueError('duplicate log path')
        self.root=_path(proc_root); self.platform=_platform(platform)
        self.clock=time.monotonic if clock is None else clock
        if not callable(self.clock): raise ValueError('monotonic clock callable required')
        self.hz=self._unit(clock_ticks,'SC_CLK_TCK'); self.page_size=self._unit(page_size,'SC_PAGESIZE')
        self.max_samples=max_samples; self.max_bytes=max_bytes
        self.samples=[]; self.stopped_reason=None; self.last_clock=None; self.next_due=None
        self.previous=None; self.logs_previous={}; self.rejected=None
        # JSON escaping can expand a valid UTF-8 path. Admit the actual encoded
        # base plus the same stop metadata reserve used for every added sample.
        if len(encode_report(self.report()))+STOP_REPORT_RESERVE_BYTES>self.max_bytes:
            raise ValueError('base report and stop reserve exceed byte budget')

    def _unit(self,value,name):
        if value is not None: return _integer(value,1,1<<30)
        if self.platform!='linux': return None
        try: return _integer(os.sysconf(name),1,1<<30)
        except (OSError,ValueError,AttributeError): return None

    def _process(self):
        identity=self.identity
        unavailable=dict(pid=identity['pid'],process_group_id=identity['process_group_id'],
            starttime_ticks=identity['starttime_ticks'],status='unavailable',reason=None)
        if self.platform!='linux': unavailable['reason']='unsupported_platform'; return unavailable
        if identity['status']!='available': return dict(unavailable,status=identity['status'],reason=identity['reason'])
        if self.rejected: return dict(unavailable,status='rejected',reason=self.rejected)
        directory=self.root/str(identity['pid'])
        try:
            first=_stat(_read(directory/'stat',MAX_PROC_BYTES),identity['pid'])
            reason=_same(first,identity)
            if reason:
                self.rejected=reason; return dict(unavailable,status='rejected',reason=reason)
            row=dict(first,status='available',errors={},rss_bytes=None,vmrss_bytes=None,vmhwm_bytes=None,
                read_bytes=None,write_bytes=None,rchar=None,wchar=None,status_threads=None)
            if self.page_size is None: row['errors']['page_size']='unavailable'
            else: row['rss_bytes']=first['rss_pages']*self.page_size
            for filename,mapping,kilobytes in (
                ('status',{b'VmRSS':'vmrss_bytes',b'VmHWM':'vmhwm_bytes',b'Threads':'status_threads'},True),
                ('io',{b'read_bytes':'read_bytes',b'write_bytes':'write_bytes',b'rchar':'rchar',b'wchar':'wchar'},False)):
                try:
                    values,errors=_fields(_read(directory/filename,MAX_PROC_BYTES),mapping,kilobytes=kilobytes)
                    row.update({mapping[k]:v for k,v in values.items()})
                    row['errors'].update({filename+'.'+k.decode():v for k,v in errors.items()})
                except (OSError,ValueError) as exc: row['errors'][filename]=_reason(exc)
            last=_stat(_read(directory/'stat',MAX_PROC_BYTES),identity['pid'])
            reason=_same(last,identity)
            if reason:
                self.rejected=reason; return dict(unavailable,status='rejected',reason=reason)
            previous=self.previous
            row.update(cpu_seconds_delta=None,read_bytes_delta=None,write_bytes_delta=None,
                delta_status='baseline' if previous is None else 'observed')
            if previous:
                if first['utime_ticks']<previous['utime_ticks'] or first['stime_ticks']<previous['stime_ticks']:
                    row['errors']['cpu_delta']='counter_rollback'
                elif self.hz is None: row['errors']['clock_ticks']='unavailable'
                else: row['cpu_seconds_delta']=(first['utime_ticks']+first['stime_ticks']-previous['utime_ticks']-previous['stime_ticks'])/self.hz
                for field in ('read_bytes','write_bytes'):
                    if row[field] is not None and previous[field] is not None:
                        if row[field]<previous[field]: row['errors'][field+'_delta']='counter_rollback'
                        else: row[field+'_delta']=row[field]-previous[field]
            self.previous=row.copy()
            if row['errors']: row['status']='partial'
            return row
        except (OSError,ValueError) as exc:
            self.previous=None
            unavailable['reason']=_reason(exc); return unavailable

    def _logs(self):
        rows=[]
        for path in self.paths:
            row=dict(path=str(path),status='unavailable',event=None,growth_bytes=None)
            try:
                info=_checked_stat(path)
                _integer(info.st_size); _integer(info.st_mtime_ns)
                current=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
                row.update(status='available',size_bytes=info.st_size,mtime_ns=info.st_mtime_ns,
                    device=info.st_dev,inode=info.st_ino)
                previous=self.logs_previous.get(path)
                if previous is None: row['event']='baseline'
                elif previous[:2]!=current[:2]: row['event']='replaced'
                elif current[2]<previous[2]: row['event']='truncated'
                else:
                    row['growth_bytes']=current[2]-previous[2]
                    row['event']='grew' if row['growth_bytes'] else 'unchanged'
                self.logs_previous[path]=current
            except (OSError,ValueError) as exc:
                row['reason']=_reason(exc); self.logs_previous.pop(path,None)
            rows.append(row)
        return rows

    def sample(self):
        """Nonblocking scheduling seam; bounded reads may still stall in the OS."""
        if self.stopped_reason: return None
        try:
            now=self.clock()
            valid=type(now) in (int,float) and abs(now)<=1e12 and math.isfinite(now)
        except (OSError,ValueError,TypeError,OverflowError): valid=False
        if not valid or self.last_clock is not None and now<self.last_clock:
            self.stopped_reason='clock_invalid'; return None
        self.last_clock=now
        if self.next_due is not None and now<self.next_due: return None
        self.next_due=now+INTERVAL_SECONDS
        row=dict(monotonic_seconds=now,process=self._process(),logs=self._logs())
        self.samples.append(row)
        # Reserve final stop metadata space; never silently trim observations.
        if len(encode_report(self.report()))+STOP_REPORT_RESERVE_BYTES>self.max_bytes:
            self.samples.pop(); self.stopped_reason='byte_budget'; return None
        if len(self.samples)>=self.max_samples: self.stopped_reason='sample_limit'
        return copy.deepcopy(row)

    def report(self):
        result=dict(schema=1,kind='bounded-process-observations',diagnostic_only=True,liveness_proven=False,
            platform=self.platform,proc_root=str(self.root),
            process_scope='one caller-pinned PID; no child/group aggregation',
            identity=self.identity,clock_ticks_per_second=self.hz,page_size_bytes=self.page_size,
            interval_seconds=INTERVAL_SECONDS,max_samples=self.max_samples,max_bytes=self.max_bytes,
            sample_count=len(self.samples),stopped_reason=self.stopped_reason,samples=self.samples,encoded_bytes=0)
        # encoded_bytes includes its own decimal representation.
        for _ in range(8):
            length=len(encode_report(result))
            if result['encoded_bytes']==length: break
            result['encoded_bytes']=length
        return copy.deepcopy(result)
