export:
	uv export --no-dev -o requirements.txt > requirements.txt

install:
	uv sync --all-extras --all-groups