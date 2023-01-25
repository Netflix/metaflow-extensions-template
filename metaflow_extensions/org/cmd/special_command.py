from metaflow._vendor import click

@click.group()
@click.pass_context
def cli(ctx):
    pass

@cli.group(help="My special command")
@click.pass_context
def specialcommand(ctx):
    # NOTE: This must match the name in the CMDS_DESC list
    pass
