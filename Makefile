.PHONY: test

test:
	bash tests/test_init.sh
	bash tests/test_init_modern.sh
	bash tests/test_plan.sh
	bash tests/test_access_policy.sh
	bash tests/test_config_validation.sh
	bash tests/test_deploy.sh
	bash tests/test_pull.sh
	bash tests/test_pull_logs.sh
	bash tests/test_diag.sh
