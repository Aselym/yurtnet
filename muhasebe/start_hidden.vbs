Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = scriptDir
objShell.Run "pythonw " & Chr(34) & scriptDir & "\app.py" & Chr(34), 0, False
