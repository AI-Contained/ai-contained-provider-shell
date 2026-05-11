package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)

const (
	exitUsage      = 1
	exitSecurity   = 2
	exitViolations = 3
	exitError      = 4
)

func main() {
	arg0 := filepath.Base(os.Args[0])
	euid := os.Geteuid()
	egid := os.Getegid()

	if euid == 0 {
		fmt.Fprintf(os.Stderr, "%s: must not run with euid 0 (root)\n", arg0)
		os.Exit(exitSecurity)
	}
	if egid == 0 {
		fmt.Fprintf(os.Stderr, "%s: must not run with egid 0 (root group)\n", arg0)
		os.Exit(exitSecurity)
	}

	fs := flag.NewFlagSet(arg0, flag.ExitOnError)
	chdir := fs.String("chdir", "", "change to `path` before running --check or exec")
	check := fs.Bool("check", false, "check for writable paths; if a command is given, exec it only if no violations found")
	fs.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [flags] [-- command [args...]]\n\n", arg0)
		fmt.Fprintf(os.Stderr, "Flags:\n")
		fs.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nExamples:\n")
		fmt.Fprintf(os.Stderr, "  %s --check\n", arg0)
		fmt.Fprintf(os.Stderr, "  %s --chdir /app --check\n", arg0)
		fmt.Fprintf(os.Stderr, "  %s --chdir /app --check -- /bin/sh -c 'echo hello'\n", arg0)
		fmt.Fprintf(os.Stderr, "  %s -- /usr/bin/ls -l\n", arg0)
	}
	fs.Parse(os.Args[1:]) //nolint:errcheck // ExitOnError handles this
	args := fs.Args()

	for _, a := range args {
		if a == "--" {
			fmt.Fprintf(os.Stderr, "%s: unexpected arguments before '--'\n", arg0)
			fs.Usage()
			os.Exit(exitUsage)
		}
	}

	if *chdir != "" {
		if err := os.Chdir(*chdir); err != nil {
			fmt.Fprintf(os.Stderr, "%s: chdir: %v\n", arg0, err)
			os.Exit(exitError)
		}
	}

	if *check {
		violations, err := checkWriteAccess(".", uint32(euid), uint32(egid))
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: check: %v\n", arg0, err)
			os.Exit(exitError)
		}
		for _, v := range violations {
			fmt.Println(v)
		}
		if len(violations) > 0 {
			os.Exit(exitViolations)
		}
		if len(args) == 0 {
			return
		}
		// violations clean — fall through to exec
	}

	if len(args) == 0 {
		fmt.Fprintf(os.Stderr, "%s: no command given\n", arg0)
		fs.Usage()
		os.Exit(exitUsage)
	}

	if err := syscall.Setresgid(egid, egid, egid); err != nil {
		fmt.Fprintf(os.Stderr, "%s: setresgid: %v\n", arg0, err)
		os.Exit(exitError)
	}
	if err := syscall.Setresuid(euid, euid, euid); err != nil {
		fmt.Fprintf(os.Stderr, "%s: setresuid: %v\n", arg0, err)
		os.Exit(exitError)
	}
	if err := syscall.Exec(args[0], args, os.Environ()); err != nil {
		fmt.Fprintf(os.Stderr, "%s: exec %q: %v\n", arg0, args[0], err)
		os.Exit(exitError)
	}
}
