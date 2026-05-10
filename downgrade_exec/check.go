package main

import (
	"io/fs"
	"path/filepath"
	"syscall"
)

func checkWriteAccess(path string, uid, gid uint32) ([]string, error) {
	var violations []string

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

		if !isWritable(stat, mode, uid, gid) {
			return nil
		}

		if d.IsDir() {
			violations = append(violations, p+"/*")
			return fs.SkipDir
		}
		violations = append(violations, p)
		return nil
	})

	if err != nil {
		return nil, err
	}
	return violations, nil
}

func isWritable(stat *syscall.Stat_t, mode fs.FileMode, uid, gid uint32) bool {
	if mode&0002 != 0 {
		return true
	}
	if mode&0020 != 0 && stat.Gid == gid {
		return true
	}
	if mode&0200 != 0 && stat.Uid == uid {
		return true
	}
	return false
}
