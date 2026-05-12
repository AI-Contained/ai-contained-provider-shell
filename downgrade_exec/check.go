package main

import (
	"io/fs"
	"path/filepath"
	"syscall"
)

type UID uint32
type GID uint32
type CheckMode fs.FileMode

const (
	CheckWritable   CheckMode = 0222
	CheckUnreadable CheckMode = 0444
)

type Violation struct {
	Path string
	Mode CheckMode
}

func checkAccess(path string, uid UID, gid GID, modes CheckMode) ([]Violation, error) {
	var violations []Violation

	err := filepath.WalkDir(path, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		info, err := d.Info()
		if err != nil {
			return err
		}

		stat := info.Sys().(*syscall.Stat_t)
		mode := info.Mode()

		var violationMode CheckMode
		if modes&CheckWritable != 0 && isWritable(stat, mode, uid, gid) {
			violationMode |= CheckWritable
		}
		if modes&CheckUnreadable != 0 && !isReadable(stat, mode, uid, gid) {
			violationMode |= CheckUnreadable
		}

		if violationMode != 0 {
			if d.IsDir() {
				violations = append(violations, Violation{p + "/*", violationMode})
				return fs.SkipDir
			}
			violations = append(violations, Violation{p, violationMode})
		}

		return nil
	})

	if err != nil {
		return nil, err
	}
	return violations, nil
}

func isWritable(stat *syscall.Stat_t, mode fs.FileMode, uid UID, gid GID) bool {
	if mode&0002 != 0 {
		return true
	}
	if mode&0020 != 0 && GID(stat.Gid) == gid {
		return true
	}
	if mode&0200 != 0 && UID(stat.Uid) == uid {
		return true
	}
	return false
}

func isReadable(stat *syscall.Stat_t, mode fs.FileMode, uid UID, gid GID) bool {
	if mode&0004 != 0 {
		return true
	}
	if mode&0040 != 0 && GID(stat.Gid) == gid {
		return true
	}
	if mode&0400 != 0 && UID(stat.Uid) == uid {
		return true
	}
	return false
}
