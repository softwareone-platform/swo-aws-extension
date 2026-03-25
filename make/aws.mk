DC = docker compose -f compose.yaml
RUN = $(DC) run --rm app
RUN_IT = $(DC) run --rm -it app

billing-journals-cur:
	$(RUN_IT) bash -c "swoext django generate_billing_journals --dry-run --month 3 --skip-date-validation --usage-source cost_usage_report"

billing-journals:
	$(RUN_IT) bash -c "swoext django generate_billing_journals --dry-run --usage-source cost_explorer"

billing-setup:
	#$(RUN_IT) bash -c "swoext django setup_cost_usage_reports --dry-run"
	#$(RUN_IT) bash -c "swoext django setup_cost_usage_reports --dry-run --agreements AGR-4945-3719-8915"
	$(RUN_IT) bash -c "swoext django setup_cost_usage_reports --dry-run"

billing-setup-aut:
	$(RUN_IT) bash -c "swoext django setup_cost_usage_reports_by_authorizations"
