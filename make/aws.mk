DC = docker compose -f compose.yaml
RUN = $(DC) run --rm app
RUN_IT = $(DC) run --rm -it app

billing-journals:
	$(RUN_IT) bash -c "swoext django generate_billing_journals"
