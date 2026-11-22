.PHONY: deps run submodule

# 1=true, 0=false
DOCKER_DISABLED=1
export DOCKER_DISABLED

MKDIR = mkdir -p $(1)
RM = rm -rf $(1)
SEPARATOR = /

deps:
	uv run sync

run:
	uv run src/main.py

submodule:
	git submodule update --init --recursive
	git submodule update --remote --merge