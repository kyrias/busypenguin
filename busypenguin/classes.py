import datetime
import traceback
from slackclient import SlackClient


class Notifier:
    def __init__(self, access_token, channel):
        self.client = SlackClient(access_token)
        self.channel = channel

    def task(self, *args, **kwargs):
        return Task(self, *args, **kwargs)


class Message:
    def __init__(self, notifier, color=None, title=None, text=None, callback_id=None, actions=None):
        self.notifier = notifier
        self.main = {'color': color,
                     'title': title,
                     'text': text,
                     'fields': [],
                     'callback_id': callback_id,
                     'actions': actions}
        self.extra = []
        self.ts = None

    def update(self, color=None, title=None, text=None, actions=None):
        for (k, v) in [('color', color), ('title', title), ('text', text), ('actions', actions)]:
            if v is not None:
                self.main[k] = v

    def add_field(self, title=None, value=None, short=None):
        self.main['fields'].append({'title': title, 'value': value, 'short': short})
        return len(self.main['fields']) - 1

    def update_field(self, index, title=None, value=None, short=None):
        for (k, v) in [('title', title), ('value', value), ('short', short)]:
            if v is not None:
                self.main['fields'][index][k] = v

    def add_attachment(self, attachment):
        self.extra.append(attachment)
        return len(self.extra) - 1

    def update_attachment(self, index, attachment):
        self.extra[index] = attachment

    def publish(self):
        attachments = [self.main] + self.extra
        if not self.ts:
            r = self.notifier.client.api_call('chat.postMessage',
                                              channel=self.notifier.channel,
                                              attachments=attachments)
            self.ts = r['ts']
        else:
            r = self.notifier.client.api_call('chat.update',
                                              channel=self.notifier.channel,
                                              ts=self.ts,
                                              attachments=attachments)


class Task:
    def __init__(self,
                 notifier,
                 color='warning',
                 title=None,
                 text=None,
                 callback_id=None,
                 actions=None,
                 status_prefix=True):
        self.notifier = notifier
        self.text = text[0].lower() + text[1:] if text else None
        self.status_prefix = status_prefix
        if status_prefix:
            text = 'Started '+self.text if self.text else None
        self.message = Message(notifier, color, title, text, callback_id, actions)
        self.done = False

    def __enter__(self):
        self.message.publish()
        self.start_time = datetime.datetime.utcnow()
        return self

    def __exit__(self, etype, value, tb):
        self.end_time = datetime.datetime.utcnow()
        total_seconds = (self.end_time - self.start_time).total_seconds()
        (minutes, seconds) = divmod(total_seconds, 60)
        self.text += f' (took {minutes:.0f}m {seconds:02.02f}s)'

        if self.done:
            self.message.publish()
            return

        if etype:
            text = 'Failed '+self.text if self.status_prefix and self.text else self.text
            self.message.update(color='danger', text=text)

            tb_attachment = {'color': 'danger',
                             'title': 'Previous task raised following exception:',
                             'text': ''.join(traceback.format_exception(etype, value, tb))}
            self.message.add_attachment(tb_attachment)
        else:
            text = 'Finished '+self.text if self.status_prefix and self.text else self.text
            self.message.update(color='good', text=text)
        self.message.publish()

    def publish(self):
        self.message.publish()

    def subtask(self, *args, **kwargs):
        return Subtask(self, *args, **kwargs)

    def update(self, *args, **kwargs):
        self.message.update(*args, **kwargs)


class Subtask:
    def __init__(self, task, text, short=False):
        self.task = task
        self.text = text
        self.short = short
        self.prefix = ':arrow_right: '

    def __enter__(self):
        self.index = self.task.message.add_field(value=self.prefix+self.text, short=self.short)
        self.task.message.publish()
        return self

    def __exit__(self, type, value, traceback):
        if type:
            self.prefix = ':x: '
        else:
            self.prefix = ':heavy_check_mark: '
        self.task.message.update_field(self.index, value=self.prefix+self.text)
        self.task.message.publish()

    def update(self, text):
        if self.text == text:
            return
        self.text = text
        self.task.message.update_field(self.index, value=self.prefix+self.text)
        self.task.message.publish()
