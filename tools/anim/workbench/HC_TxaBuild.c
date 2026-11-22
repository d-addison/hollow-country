// DEPRECATED, RETIRED FOR CLIP BUILDS (2026-11-22). The authoritative route for infected clips
// is the standard-library SET6 writer (tools/anim/anm.py via tools/anim/build_infected_clips.py,
// see docs/ANIMATION_PIPELINE.md). That writer needs no Windows, Workbench or GUI and is unit tested.
// This plugin was never observed running (WorkbenchPlugin.RunCommandline has not been seen
// executing under WorkbenchApp.exe), is not part of any build or package route, and is kept only as
// prior art for a future Workbench probe (for example a non-SET6 format). Do not use it for clips.
// Hollow Country headless TXA -> ANM builder for DayZ Workbench (DayZ Tools).
// Our own source. Registers (first run) or rebuilds (later runs) every .txa listed in the
// args file, one absolute Windows path per line, then exits.
//
// Usage (from the DayZ Tools Bin/Workbench directory, see docs/ANIMATION_PIPELINE.md):
//   WorkbenchApp.exe -gproj=<work>\hc_anim.gproj -wbmodule=ResourceManager -plugin=HC_TxaBuild -hcArgs=<work>\hc_args.txt
//
// API (DayZ Tools Workbench dta/scripts.pbo):
//   1_Core/WorkbenchAPI/Modules/ResourceManager.c  RegisterResourceFile, RebuildResourceFile, WaitForFile
//   1_Core/WorkbenchAPI/Modules/WBModuleDef.c      GetCmdLine
//   1_Core/WorkbenchAPI/Workbench.c                GetModule, Exit
//   1_Core/WorkbenchAPI/Plugins/WorkbenchPlugin.c  RunCommandline
//   1_Core/proto/EnSystem.c:397/417/443/501        FileExist, OpenFile, CloseFile, FGets
#ifdef WORKBENCH
[WorkbenchPluginAttribute("HC TXA Build", "Build Hollow Country .txa clips into .anm", "", "", {"ResourceManager"})]
class HC_TxaBuild: WorkbenchPlugin
{
	void BuildOne(ResourceManager rm, string line)
	{
		bool ok;
		string mode = "register";
		if (FileExist(line + ".meta"))
		{
			mode = "rebuild";
			rm.RebuildResourceFile(line, "PC", false);
			ok = true;
		}
		else
		{
			ok = rm.RegisterResourceFile(line, true);
		}
		bool waited = rm.WaitForFile(line, 10000);
		Print("[HC_TxaBuild] " + mode + " " + line + " ok=" + ok.ToString() + " waited=" + waited.ToString());
	}

	override void RunCommandline()
	{
		ResourceManager rm = Workbench.GetModule(ResourceManager);
		string argsPath;
		if (!rm.GetCmdLine("-hcArgs", argsPath))
		{
			Print("[HC_TxaBuild] missing -hcArgs=<file>");
			Workbench.Exit(2);
			return;
		}
		argsPath.Replace("\"", "");
		FileHandle f = OpenFile(argsPath, FileMode.READ);
		if (!f)
		{
			Print("[HC_TxaBuild] cannot open " + argsPath);
			Workbench.Exit(3);
			return;
		}
		string line;
		int count = 0;
		while (FGets(f, line) >= 0)
		{
			line.TrimInPlace();
			if (line.Length() < 5)
				continue;
			BuildOne(rm, line);
			count++;
		}
		CloseFile(f);
		Print("[HC_TxaBuild] done files=" + count.ToString());
		Workbench.Exit(0);
	}
}
#endif
