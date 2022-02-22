import asyncio

import click

from . import client, models

class ClientContext:
    def __init__(self, host_url: str):
        self.host_url = host_url
        self.loop = asyncio.get_event_loop()
        self.client = None
        self.context_vars = {}

    def __getitem__(self, key):
        return self.context_vars[key]

    def __setitem__(self, key, item):
        self.context_vars[key] = item

    def update(self, other_dict):
        self.context_vars.update(other_dict)

    def call_client(self, method_name: str, *args):
        m = getattr(self.client, method_name)
        if len(args):
            coro = m(*args)
        else:
            coro = m()
        return self.loop.run_until_complete(coro)

    def __enter__(self):
        self.client = client.ApiClient(self.host_url)
        self.loop.run_until_complete(self.client.__aenter__())
        return self

    def __exit__(self, *args):
        try:
            self.loop.run_until_complete(self.client.__aexit__())
        finally:
            self.loop.close()



@click.group()
@click.argument('url', type=str)
@click.pass_context
def cli(ctx, **kwargs):
    client_context = ClientContext(kwargs['url'])
    ctx.obj = ctx.with_resource(client_context)
    ctx.obj.update({k:v for k,v in kwargs.items()})

@cli.command()
@click.pass_context
def hostname(ctx):
    h = ctx.obj.call_client('get_hostname')
    hurl = f'http://{h}.local'
    click.echo(f'{h} -> {hurl}')

@cli.command(name='reboot')
@click.pass_context
def cli_reboot(ctx):
    ctx.obj.call_client('reboot')
    click.echo('Device rebooting')

@cli.command(name='restart')
@click.pass_context
def cli_restart(ctx):
    ctx.obj.call_client('restart')
    click.echo('Video system restarting')

@cli.group()
@click.pass_context
def mode(ctx):
    pass

@mode.command(name='get')
@click.pass_context
def cli_mode_get(ctx):
    current_mode = ctx.obj.call_client('get_operation_mode')
    click.echo(f'Current Mode: "{current_mode.name}"')

@mode.command(name='set')
@click.argument('new_mode', type=click.Choice(['encode', 'decode']))
@click.pass_context
def cli_mode_set(ctx, new_mode):
    ctx.obj.call_client('set_operation_mode', new_mode)
    # click.echo(f'Mode set to "{new_mode}".  Rebooting device...')
    # ctx.obj.call_client('reboot')

@cli.group(name='audio')
@click.pass_context
def cli_audio(ctx):
    pass

@cli_audio.command(name='get')
@click.pass_context
def cli_audio_get(ctx):
    audio = ctx.obj.call_client('get_audio_setup')
    click.echo(str(audio))

@cli.group(name='output')
@click.pass_context
def cli_output(ctx):
    pass

@cli_output.command(name='get')
@click.pass_context
def cli_output_get(ctx):
    output = ctx.obj.call_client('get_video_output')
    click.echo(f'Video output: "{output.name}"')

@cli_output.command(name='set')
@click.argument('mode', type=click.Choice(['sdi', 'hdmi']))
@click.pass_context
def cli_output_set(ctx, mode):
    ctx.obj.call_client('set_video_output', mode)
    click.echo(f'Video output set to "{mode.name}"')

@cli.group()
@click.pass_context
def source(ctx):
    pass

@source.command(name='refresh')
@click.pass_context
def source_refresh(ctx):
    click.echo('Refreshing...')
    ctx.obj.call_client('refresh_sources')

    click.echo('Available Sources:')
    source_iter = ctx.obj.call_client('list_sources')
    for src in source_iter:
        click.echo(src.format())

@source.command(name='current')
@click.pass_context
def current_source(ctx):
    src = ctx.obj.call_client('get_source')
    click.echo(f'Current Source:')
    click.echo(src.format())

@source.command(name='list')
@click.pass_context
def cli_list_sources(ctx):
    click.echo('Available Sources:')

    source_iter = ctx.obj.call_client('list_sources')
    for src in source_iter:
        click.echo(src.format())

@source.command(name='set')
@click.argument('source', type=str)
@click.pass_context
def cli_set_source(ctx, source):
    if source.isdigit():
        source = int(source)
    ctx.obj.call_client('set_source', source)

    source_iter = ctx.obj.call_client('list_sources')
    for src in source_iter:
        click.echo(src.format())

if __name__ == '__main__':
    cli()
