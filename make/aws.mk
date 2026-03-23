DC = docker compose -f compose.yaml
RUN = $(DC) run --rm app
RUN_IT = $(DC) run --rm -it app

billing-journals:
	$(RUN_IT) bash -c "swoext django generate_billing_journals --dry-run --usage-source cost_explorer"
	#$(RUN_IT) bash -c "swoext django generate_billing_journals --dry-run --usage-source cost_usage_report"

billing-setup:
	$(RUN_IT) bash -c "swoext django setup_cost_usage_reports --dry-run"
	#$(RUN_IT) bash -c "swoext django setup_cost_usage_reports --agreements AGR-4945-3719-8915"
