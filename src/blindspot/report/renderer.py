from jinja2 import Environment, PackageLoader

from blindspot.report.context import DepartureContext, ReportContext


class ReportRenderer:
    def __init__(self) -> None:
        self.env = Environment(
            loader=PackageLoader("blindspot.report", "templates"),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["pct"] = lambda v: f"{v * 100:.0f}%"
        self.env.filters["days"] = lambda v: f"{v:.0f}"

    def render(self, ctx: ReportContext) -> str:
        template = self.env.get_template("report.html.j2")
        return template.render(ctx=ctx)

    def render_departure(self, ctx: DepartureContext) -> str:
        template = self.env.get_template("departure.html.j2")
        return template.render(ctx=ctx)
