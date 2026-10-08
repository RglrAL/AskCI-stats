-- AskCI Feed Export: drop QA feed exports (qa-feed_*.csv) on this app.
-- Redacts them, compares the daily aggregates with the dashboard's current files, writes the
-- results to a review folder beside the dropped file, and offers to copy them into the dashboard.
-- Build:  osacompile -o "tools/AskCI Feed Export.app" tools/feed_droplet.applescript

property defaultRepo : "/Users/alan/AskCI-stats"

on run
	set picked to choose file with prompt "Choose one or more AskCI QA feed exports (qa-feed_*.csv)" with multiple selections allowed
	open picked
end run

on open theFiles
	set repo to my findRepo()
	set args to ""
	set firstDir to ""
	repeat with f in theFiles
		set p to POSIX path of f
		if p ends with ".csv" then
			set args to args & " " & quoted form of p
			if firstDir = "" then set firstDir to do shell script "dirname " & quoted form of p
		end if
	end repeat
	if args = "" then
		display alert "Nothing to do" message "Drop one or more .csv feed exports on this app."
		return
	end if
	set stamp to do shell script "date +%Y-%m-%d_%H%M"
	set outDir to firstDir & "/askci-export-" & stamp
	try
		set summary to do shell script "/bin/sh " & quoted form of (repo & "/tools/feed_export.sh") & " " & quoted form of outDir & args
	on error errMsg
		display alert "Export failed" message errMsg as critical
		return
	end try
	set choice to button returned of (display dialog summary with title "AskCI Feed Export" buttons {"Done", "Open folder", "Copy into dashboard…"} default button "Open folder")
	if choice = "Open folder" then
		do shell script "open " & quoted form of outDir
	else if choice = "Copy into dashboard…" then
		set ok to button returned of (display dialog "Replace usage.csv and categories.csv in" & return & repo & return & return & "with the generated files, and add usage-hours.csv and categories-daily.csv? The redacted feed is not copied." buttons {"Cancel", "Replace"} default button "Cancel" with icon caution)
		if ok = "Replace" then
			do shell script "cp " & quoted form of (outDir & "/usage.csv") & " " & quoted form of (outDir & "/usage-hours.csv") & " " & quoted form of (outDir & "/categories.csv") & " " & quoted form of (outDir & "/categories-daily.csv") & " " & quoted form of (repo & "/")
			display dialog "Copied. Reload the dashboard to see the new data; commit when you are happy with it." buttons {"OK"} default button "OK"
		end if
	end if
end open

-- The dashboard folder: the app's grandparent when it lives in <repo>/tools, else the default.
on findRepo()
	try
		set appPath to POSIX path of (path to me)
		set candidate to do shell script "cd " & quoted form of appPath & "/../.. && pwd"
		do shell script "test -f " & quoted form of (candidate & "/tools/make_usage.py")
		return candidate
	on error
		return defaultRepo
	end try
end findRepo
