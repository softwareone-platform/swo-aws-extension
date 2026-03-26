generate-billing-journals: ## Run billing journal generation
	$(RUN) bash -c "swoext django generate_billing_journals --dry-run --year 2026 --month 3 --usage-source cost_usage_report"
	#$(RUN) bash -c "swoext django generate_billing_journals --year 2026 --month 3 --usage-source cost_explorer"

generate-billing-help: ## Run billing journal generation
	$(RUN) bash -c "swoext django generate_billing_journals --help"


