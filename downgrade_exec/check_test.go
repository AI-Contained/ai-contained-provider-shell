package main

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

const (
	nobody  UID = 65534
	nogroup GID = 65534
)

// chmod sets mode on path and schedules a restore to 0755 after the current
// Ginkgo node so that GinkgoT().TempDir() can remove the tree.
func chmod(path string, mode fs.FileMode) {
	Expect(os.Chmod(path, mode)).To(Succeed())
	DeferCleanup(os.Chmod, path, fs.FileMode(0755))
}

func credentialsFor(who string) (UID, GID) {
	switch who {
	case "owner":
		return UID(os.Getuid()), GID(os.Getgid())
	case "group":
		return nobody, GID(os.Getgid())
	default: // "world"
		return nobody, nogroup
	}
}

type modeCase struct {
	expected_mode CheckMode
	who           string
	base          fs.FileMode
	violation     func(base fs.FileMode) fs.FileMode
	safe          func(base fs.FileMode) fs.FileMode
}

var modeCases = []modeCase{
	{CheckWritable, "world", 0555,
		func(b fs.FileMode) fs.FileMode { return b | 0002 },
		func(b fs.FileMode) fs.FileMode { return b &^ 0002 },
	},
	{CheckWritable, "group", 0550,
		func(b fs.FileMode) fs.FileMode { return b | 0020 },
		func(b fs.FileMode) fs.FileMode { return b &^ 0020 },
	},
	{CheckWritable, "owner", 0500,
		func(b fs.FileMode) fs.FileMode { return b | 0200 },
		func(b fs.FileMode) fs.FileMode { return b &^ 0200 },
	},
	{CheckUnreadable, "world", 0777,
		func(b fs.FileMode) fs.FileMode { return b &^ 0004 },
		func(b fs.FileMode) fs.FileMode { return b | 0004 },
	},
	{CheckUnreadable, "group", 0770,
		func(b fs.FileMode) fs.FileMode { return b &^ 0040 },
		func(b fs.FileMode) fs.FileMode { return b | 0040 },
	},
	{CheckUnreadable, "owner", 0700,
		func(b fs.FileMode) fs.FileMode { return b &^ 0400 },
		func(b fs.FileMode) fs.FileMode { return b | 0400 },
	},
	// 0553: world -wx — simultaneously writable (write bit set) and unreadable (read bit absent)
	{CheckWritable | CheckUnreadable, "world", 0555,
		func(b fs.FileMode) fs.FileMode { return (b | 0002) &^ 0004 },
		func(b fs.FileMode) fs.FileMode { return (b &^ 0002) | 0004 },
	},
	// 0620: group -w- with no world read — group-writable and unreadable by group+world
	{CheckWritable | CheckUnreadable, "group", 0640,
		func(b fs.FileMode) fs.FileMode { return (b | 0020) &^ 0040 },
		func(b fs.FileMode) fs.FileMode { return (b &^ 0020) | 0040 },
	},
	// 0300: owner -wx — simultaneously writable (write bit set) and unreadable (read bit absent)
	{CheckWritable | CheckUnreadable, "owner", 0500,
		func(b fs.FileMode) fs.FileMode { return (b | 0200) &^ 0400 },
		func(b fs.FileMode) fs.FileMode { return (b &^ 0200) | 0400 },
	},
}

var _ = Describe("checkAccess", func() {
	for _, mc := range modeCases {
		mc := mc
		uid, gid := credentialsFor(mc.who)

		Context(fmt.Sprintf("expected_mode=0%o who=%s", mc.expected_mode, mc.who), func() {
			var root string

			BeforeEach(func() {
				root = GinkgoT().TempDir()
			})

			It("returns no violations when all entries are safe", func() {
				f := filepath.Join(root, "file.txt")
				Expect(os.WriteFile(f, []byte("x"), mc.safe(mc.base))).To(Succeed())
				chmod(root, mc.safe(mc.base))

				violations, err := checkAccess(root, uid, gid, mc.expected_mode)
				Expect(err).NotTo(HaveOccurred())
				Expect(violations).To(BeEmpty())
			})

			It("reports root/* and does not recurse when root is a violation", func() {
				sub := filepath.Join(root, "sub")
				Expect(os.Mkdir(sub, 0755)).To(Succeed())
				chmod(root, mc.violation(mc.base))

				violations, err := checkAccess(root, uid, gid, mc.expected_mode)
				Expect(err).NotTo(HaveOccurred())
				Expect(violations).To(ConsistOf(Violation{root + "/*", mc.expected_mode}))
			})

			It("reports dir/* and does not recurse for a violation subdirectory", func() {
				sub := filepath.Join(root, "data")
				nested := filepath.Join(sub, "nested")
				Expect(os.MkdirAll(nested, 0755)).To(Succeed())
				chmod(sub, mc.violation(mc.base))
				chmod(root, mc.safe(mc.base))

				violations, err := checkAccess(root, uid, gid, mc.expected_mode)
				Expect(err).NotTo(HaveOccurred())
				Expect(violations).To(ConsistOf(Violation{sub + "/*", mc.expected_mode}))
			})

			It("reports a violation file", func() {
				f := filepath.Join(root, "file.txt")
				Expect(os.WriteFile(f, []byte("x"), mc.safe(mc.base))).To(Succeed())
				chmod(f, mc.violation(mc.base))
				chmod(root, mc.safe(mc.base))

				violations, err := checkAccess(root, uid, gid, mc.expected_mode)
				Expect(err).NotTo(HaveOccurred())
				Expect(violations).To(ConsistOf(Violation{f, mc.expected_mode}))
			})

			It("reports all violation siblings without recursing into violation dirs", func() {
				b1 := filepath.Join(root, "b1")
				Expect(os.Mkdir(b1, 0755)).To(Succeed())
				Expect(os.WriteFile(filepath.Join(b1, "c.txt"), []byte("x"), mc.safe(mc.base))).To(Succeed())
				chmod(b1, mc.violation(mc.base))

				b2 := filepath.Join(root, "b2")
				Expect(os.Mkdir(b2, 0755)).To(Succeed())
				Expect(os.WriteFile(filepath.Join(b2, "c.txt"), []byte("x"), mc.safe(mc.base))).To(Succeed())
				chmod(b2, mc.safe(mc.base))

				b3 := filepath.Join(root, "b3.txt")
				Expect(os.WriteFile(b3, []byte("x"), mc.safe(mc.base))).To(Succeed())
				chmod(b3, mc.violation(mc.base))

				chmod(root, mc.safe(mc.base))

				violations, err := checkAccess(root, uid, gid, mc.expected_mode)
				Expect(err).NotTo(HaveOccurred())
				Expect(violations).To(ConsistOf(
					Violation{b1 + "/*", mc.expected_mode},
					Violation{b3, mc.expected_mode},
				))
			})
		})
	}

	It("returns an error for a non-existent path", func() {
		root := GinkgoT().TempDir()
		_, err := checkAccess(filepath.Join(root, "nonexistent"), nobody, nogroup, CheckWritable)
		Expect(err).To(HaveOccurred())
	})
})
