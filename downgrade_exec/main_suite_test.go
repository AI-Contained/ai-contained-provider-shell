package main

import (
	"testing"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

func TestDowngradeExec(t *testing.T) {
	RegisterFailHandler(Fail)
	RunSpecs(t, "downgrade_exec Suite")
}
