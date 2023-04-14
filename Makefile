

VERSION := $(shell grep ^version: galaxy.yml | cut -d" " -f2)
TARGET  := ibre5041-ansible_oracle_modules-$(VERSION).tar.gz

all: build install

build:
	ansible-galaxy collection build --force

install:
	ansible-galaxy collection install --force ${TARGET}
	cp -f tests/integration/integration_config.yml ~/.ansible/collections/ansible_collections/ibre5041/ansible_oracle_modules/tests/integration/

clean:
	rm -f ibre5041-ansible_oracle_modules-*.tar.gz


# test individual role: make test ROLE=test_oracle_profile
test:
	cd ~/.ansible/collections/ansible_collections/ibre5041/ansible_oracle_modules/tests/integration && ansible-test integration $(ROLE)


all:
