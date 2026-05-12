package main

import "io/fs"

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
	return nil, nil
}
