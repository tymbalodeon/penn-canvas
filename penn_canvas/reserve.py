import enable_reserve
import reserve_report
import typer

app = typer.Typer()
app.add_typer(enable_reserve.app, name="enable")
app.add_typer(reserve_report.app, name="report")

if __name__ == "__main__":
    app()
