class CronTrigger:
    def __init__(self, expr=None, timezone=None):
        self.expr = expr
        self.timezone = timezone

    @classmethod
    def from_crontab(cls, expr, timezone=None):
        return cls(expr, timezone)

    def __str__(self):
        return self.expr or ""
