// Original HC tooling. Installed DayZ Tools dta/scripts.pbo declares these APIs.
// ExecuteAction's menu path/completion behaviour still needs native qualification.
// The driver requires the ENGINE's validation-success log, never this receipt alone.
#ifdef WORKBENCH
[WorkbenchPluginAttribute("HC Compile Check", "Validate scratch project scripts", "", "", {"ScriptEditor"})]
class HC_CompileCheck: WorkbenchPlugin
{
	override void RunCommandline()
	{
		ScriptEditor editor = Workbench.GetModule(ScriptEditor);
		if (!editor)
		{
			Print("[HC CompileCheck] no_script_editor");
			Workbench.Exit(2);
			return;
		}
		string actionPath;
		if (!editor.GetCmdLine("-hcCompileAction", actionPath))
		{
			Print("[HC CompileCheck] missing_action");
			Workbench.Exit(2);
			return;
		}
		actionPath.Replace("\"", "");
		array<string> menuPath = new array<string>;
		actionPath.Split("/", menuPath);
		bool dispatched = editor.ExecuteAction(menuPath);
		if (!dispatched)
		{
			Print("[HC CompileCheck] action_refused");
			Workbench.Exit(2);
			return;
		}
		Print("[HC CompileCheck] action_returned");
		Workbench.Exit(0);
	}
}
#endif
