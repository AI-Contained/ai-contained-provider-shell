package main

import (
	"os"
	"path/filepath"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

var _ = Describe("checkWriteAccess", func() {
	var (
		root string
		uid  uint32
		gid  uint32
	)

	BeforeEach(func() {
		root = GinkgoT().TempDir()
		// use nobody — world-writable bits will be caught regardless of ownership
		uid = 65534
		gid = 65534
	})

	Context("when no entries are writable", func() {
		It("returns empty for a read-only root", func() {
			Expect(os.Chmod(root, 0555)).To(Succeed())
			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(BeEmpty())
		})

		It("returns empty for a read-only nested structure", func() {
			sub := filepath.Join(root, "sub")
			Expect(os.Mkdir(sub, 0755)).To(Succeed())
			Expect(os.Chmod(sub, 0555)).To(Succeed())
			Expect(os.Chmod(root, 0555)).To(Succeed())
			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(BeEmpty())
		})
	})

	Context("when the root itself is world-writable", func() {
		It("reports root/* and does not recurse", func() {
			sub := filepath.Join(root, "sub")
			Expect(os.Mkdir(sub, 0777)).To(Succeed())
			Expect(os.Chmod(root, 0777)).To(Succeed())

			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			// root is the first violation — sub must not appear
			Expect(violations).To(ConsistOf(root + "/*"))
		})
	})

	Context("when a subdirectory is world-writable", func() {
		It("reports dir/* and does not recurse into it", func() {
			sub := filepath.Join(root, "data")
			nested := filepath.Join(sub, "nested")
			Expect(os.MkdirAll(nested, 0755)).To(Succeed())
			Expect(os.Chmod(sub, 0777)).To(Succeed())
			Expect(os.Chmod(root, 0555)).To(Succeed())

			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(ConsistOf(sub + "/*"))
		})
	})

	Context("when a file is world-writable", func() {
		It("reports the file path", func() {
			f := filepath.Join(root, "config.txt")
			Expect(os.WriteFile(f, []byte("x"), 0644)).To(Succeed())
			Expect(os.Chmod(f, 0666)).To(Succeed())
			Expect(os.Chmod(root, 0555)).To(Succeed())

			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(ConsistOf(f))
		})
	})

	Context("when multiple siblings are writable", func() {
		It("reports all writable siblings without descending into writable dirs", func() {
			b1 := filepath.Join(root, "b1")
			Expect(os.Mkdir(b1, 0755)).To(Succeed())
			Expect(os.WriteFile(filepath.Join(b1, "c.txt"), []byte("x"), 0644)).To(Succeed())
			Expect(os.Chmod(b1, 0777)).To(Succeed())

			b2 := filepath.Join(root, "b2")
			Expect(os.Mkdir(b2, 0555)).To(Succeed())
			Expect(os.WriteFile(filepath.Join(b2, "c.txt"), []byte("x"), 0444)).To(Succeed())

			b3 := filepath.Join(root, "b3.txt")
			Expect(os.WriteFile(b3, []byte("x"), 0644)).To(Succeed())
			Expect(os.Chmod(b3, 0666)).To(Succeed())

			Expect(os.Chmod(root, 0555)).To(Succeed())

			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(ConsistOf(b1+"/*", b3))
		})
	})

	Context("when the entry is owned by the given uid", func() {
		BeforeEach(func() {
			uid = uint32(os.Getuid())
			gid = uint32(os.Getgid())
		})

		It("reports a directory writable by its owner", func() {
			sub := filepath.Join(root, "owned")
			Expect(os.Mkdir(sub, 0700)).To(Succeed())
			Expect(os.Chmod(root, 0555)).To(Succeed())

			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(ConsistOf(sub + "/*"))
		})

		It("reports a file writable by its owner", func() {
			f := filepath.Join(root, "owned.txt")
			Expect(os.WriteFile(f, []byte("x"), 0600)).To(Succeed())
			Expect(os.Chmod(root, 0555)).To(Succeed())

			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(ConsistOf(f))
		})
	})

	Context("when the entry is group-writable and gid matches", func() {
		BeforeEach(func() {
			uid = 65534
			gid = uint32(os.Getgid())
		})

		It("reports a directory writable by group", func() {
			sub := filepath.Join(root, "grp")
			Expect(os.Mkdir(sub, 0755)).To(Succeed())
			Expect(os.Chmod(sub, 0770)).To(Succeed())
			Expect(os.Chmod(root, 0555)).To(Succeed())

			violations, err := checkWriteAccess(root, uid, gid)
			Expect(err).NotTo(HaveOccurred())
			Expect(violations).To(ConsistOf(sub + "/*"))
		})
	})

	It("returns an error for a non-existent path", func() {
		_, err := checkWriteAccess(filepath.Join(root, "nonexistent"), uid, gid)
		Expect(err).To(HaveOccurred())
	})
})
