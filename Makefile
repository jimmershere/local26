.PHONY: test

test:
	bash tests/test_init.sh
	bash tests/test_plan.sh
	bash tests/test_deploy.sh
