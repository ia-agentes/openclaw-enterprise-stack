install:
	bash bootstrap/install.sh

check:
	bash bootstrap/check.sh

dirs:
	bash bootstrap/directories.sh

docker:
	bash bootstrap/docker.sh

generate:
	python3 scripts/generate.py

deploy:
	bash scripts/deploy.sh

doctor:
	bash scripts/doctor.sh
