

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

# Copier la config Docker XE dans le répertoire d'installation
integration-config-docker: install
	cp -f tests/integration/integration_config.yml.docker \
	   ~/.ansible/collections/ansible_collections/ibre5041/ansible_oracle_modules/tests/integration/integration_config.yml

# Copier la config Docker EE dans le répertoire d'installation
integration-config-ee: install
	cp -f tests/integration/integration_config.yml.ee \
	   ~/.ansible/collections/ansible_collections/ibre5041/ansible_oracle_modules/tests/integration/integration_config.yml

# Lancer tous les tests compatibles conteneur Oracle XE
# Pré-requis : docker compose up -d  (avec gvenzl/oracle-xe:21-slim)
test-docker: build integration-config-docker
	@FAILED=""; \
	for ROLE in \
	    test_oracle_ping test_oracle_tnsnames test_oracle_sql \
	    test_oracle_awr test_oracle_directory test_oracle_profile \
	    test_oracle_role test_oracle_user test_oracle_tablespace \
	    test_oracle_parameter test_oracle_grant test_oracle_pdb \
	    test_oracle_facts \
	    test_oracle_wallet test_oracle_orapki \
	    test_oracle_dataguard; do \
	  echo ""; \
	  echo "=== $$ROLE ==="; \
	  $(MAKE) test ROLE=$$ROLE || FAILED="$$FAILED $$ROLE"; \
	done; \
	if [ -n "$$FAILED" ]; then echo "FAILED:$$FAILED"; exit 1; fi

# Lancer tous les tests avec Oracle EE (TDE, orapki, etc.)
# Pré-requis : docker compose up -d  (avec container-registry.oracle.com/database/enterprise:latest)
test-docker-ee: build integration-config-ee
	@FAILED=""; \
	for ROLE in \
	    test_oracle_ping test_oracle_tnsnames test_oracle_sql \
	    test_oracle_awr test_oracle_directory test_oracle_profile \
	    test_oracle_role test_oracle_user test_oracle_tablespace \
	    test_oracle_parameter test_oracle_grant test_oracle_pdb \
	    test_oracle_facts \
	    test_oracle_wallet test_oracle_orapki \
	    test_oracle_dataguard; do \
	  echo ""; \
	  echo "=== $$ROLE ==="; \
	  $(MAKE) test ROLE=$$ROLE || FAILED="$$FAILED $$ROLE"; \
	done; \
	if [ -n "$$FAILED" ]; then echo "FAILED:$$FAILED"; exit 1; fi


# test individual role: make test ROLE=test_oracle_profile
test:
	cd ~/.ansible/collections/ansible_collections/ibre5041/ansible_oracle_modules/tests/integration && ansible-test integration $(ROLE)

check:	build
	python3 -m galaxy_importer.main ${TARGET}

doc:
	antsibull-changelog release
	echo "place changes into changelogs/changelog.yaml"
	antsibull-changelog lint-changelog-yaml changelogs/changelog.yaml
	antsibull-changelog generate
all:
