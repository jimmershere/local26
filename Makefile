.PHONY: test

test:
	bash tests/test_init.sh
	bash tests/test_init_modern.sh
	bash tests/test_plan.sh
	bash tests/test_deploy.sh
	bash tests/test_pull_logs.sh
