' BSMQ Tool Launcher — chay server ngam, mo trinh duyet tu dong
Dim ws, dir
Set ws = CreateObject("WScript.Shell")
dir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
' Chay run.bat an (windowStyle=0 = hidden)
ws.Run "cmd /c """ & dir & "run.bat""", 0, False
