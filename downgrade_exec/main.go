package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"

	"golang.org/x/sys/unix"
)

const (
	exitUsage      = 1
	exitSecurity   = 2
	exitViolations = 3
	exitError      = 4
)

// checkFlag implements flag.Value for --check=writable,unreadable.
type checkFlag struct {
	modes CheckMode
}

func (f *checkFlag) String() string {
	var parts []string
	if f.modes&CheckWritable != 0 {
		parts = append(parts, "writable")
	}
	if f.modes&CheckUnreadable != 0 {
		parts = append(parts, "unreadable")
	}
	return strings.Join(parts, ",")
}

func (f *checkFlag) Set(s string) error {
	if s == "" {
		return fmt.Errorf("value required (valid: writable, unreadable)")
	}
	f.modes = 0
	for _, token := range strings.Split(s, ",") {
		switch strings.TrimSpace(token) {
		case "writable":
			f.modes |= CheckWritable
		case "unreadable":
			f.modes |= CheckUnreadable
		default:
			return fmt.Errorf("unknown check mode %q (valid: writable, unreadable)", token)
		}
	}
	return nil
}

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

	// Drop privileges immediately — lock all three (real, effective, saved) to nobody.
	// This ensures both the --check walk and the final exec run under the same identity.
	// Supplementary groups must be dropped first: once Setresuid runs, CAP_SETGID is
	// gone and setgroups(2) would fail with EPERM.
	if err := syscall.Setgroups([]int{}); err != nil {
		fmt.Fprintf(os.Stderr, "%s: setgroups: %v\n", arg0, err)
		os.Exit(exitError)
	}
	if err := syscall.Setresgid(egid, egid, egid); err != nil {
		fmt.Fprintf(os.Stderr, "%s: setresgid: %v\n", arg0, err)
		os.Exit(exitError)
	}
	if err := syscall.Setresuid(euid, euid, euid); err != nil {
		fmt.Fprintf(os.Stderr, "%s: setresuid: %v\n", arg0, err)
		os.Exit(exitError)
	}

	// Assert the drop was complete: all three of real/effective/saved must equal
	// the target identity and no supplementary groups must remain.
	if ruid, euid2, suid := unix.Getresuid(); ruid != euid || euid2 != euid || suid != euid {
		fmt.Fprintf(os.Stderr, "%s: uid assertion failed after setresuid\n", arg0)
		os.Exit(exitSecurity)
	}
	if rgid, egid2, sgid := unix.Getresgid(); rgid != egid || egid2 != egid || sgid != egid {
		fmt.Fprintf(os.Stderr, "%s: gid assertion failed after setresgid\n", arg0)
		os.Exit(exitSecurity)
	}
	if groups, err := syscall.Getgroups(); err != nil || len(groups) != 0 {
		fmt.Fprintf(os.Stderr, "%s: supplementary groups remain after setgroups\n", arg0)
		os.Exit(exitSecurity)
	}

	check := &checkFlag{}
	fs := flag.NewFlagSet(arg0, flag.ExitOnError)
	chdir := fs.String("chdir", "", "change to `path` before running --check or exec")
	fs.Var(check, "check", "comma-separated check modes: writable, unreadable")
	fs.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [flags] [-- command [args...]]\n\n", arg0)
		fmt.Fprintf(os.Stderr, "Flags:\n")
		fs.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nExamples:\n")
		fmt.Fprintf(os.Stderr, "  %s --check=writable\n", arg0)
		fmt.Fprintf(os.Stderr, "  %s --chdir /app --check=writable,unreadable\n", arg0)
		fmt.Fprintf(os.Stderr, "  %s --chdir /app --check=writable -- /bin/sh -c 'echo hello'\n", arg0)
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

	if check.modes != 0 {
		violations, err := checkAccess(".", UID(euid), GID(egid), check.modes)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: check: %v\n", arg0, err)
			os.Exit(exitError)
		}
		reportViolations(arg0, violations, CheckWritable, "writable")
		reportViolations(arg0, violations, CheckUnreadable, "unreadable")
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

	if err := syscall.Exec(args[0], args, os.Environ()); err != nil {
		fmt.Fprintf(os.Stderr, "%s: exec %q: %v\n", arg0, args[0], err)
		os.Exit(exitError)
	}
}

func reportViolations(arg0 string, violations []Violation, mode CheckMode, label string) {
	var paths []string
	for _, v := range violations {
		if v.Mode&mode != 0 {
			paths = append(paths, v.Path)
		}
	}
	if len(paths) == 0 {
		return
	}
	fmt.Fprintf(os.Stderr, "%s: security check failed: %d %s path(s) detected:\n", arg0, len(paths), label)
	for _, p := range paths {
		fmt.Fprintf(os.Stderr, "  %s\n", p)
	}
}
