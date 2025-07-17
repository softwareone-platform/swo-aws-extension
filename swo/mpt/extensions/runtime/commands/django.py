import click

from swo.mpt.extensions.runtime.tracer import dynamic_trace_span


@dynamic_trace_span(lambda *args: f"Running Django command {args[1]}")
def execute(ctx, management_args):
    from django.core.management import execute_from_command_line

    execute_from_command_line(argv=[ctx.command_path] + list(management_args))


@click.command(add_help_option=False, context_settings=dict(ignore_unknown_options=True))
@click.argument("management_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def django(ctx, management_args):
    """Execute Django subcommands."""
    from swo.mpt.extensions.runtime.initializer import initialize

    initialize({})
    execute(ctx, management_args)
