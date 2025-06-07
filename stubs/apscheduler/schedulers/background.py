class Job:
    def __init__(self, id, func, trigger, args):
        self.id = id
        self.func = func
        self.trigger = trigger
        self.args = args

class BackgroundScheduler:
    def __init__(self, timezone=None):
        self.jobs = {}

    def add_job(self, func, trigger=None, args=None, id=None, replace_existing=False):
        self.jobs[id] = Job(id, func, trigger, args or [])

    def get_jobs(self):
        return list(self.jobs.values())

    def get_job(self, id):
        return self.jobs.get(id)

    def remove_job(self, id):
        self.jobs.pop(id, None)

    def start(self):
        pass

    def shutdown(self):
        self.jobs.clear()
