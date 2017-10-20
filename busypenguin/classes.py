import datetime
import traceback
from slackclient import SlackClient


class Notifier:
    '''
    The Notifier class is the base busypenguin class.  It takes a Slack bot
    access token, and a channel ID that all messages will be posted to.
    '''
    def __init__(self, access_token, channel):
        self.client = SlackClient(access_token)
        self.channel = channel

    def task(self, *args, **kwargs):
        '''Creates a :py:class:`Task` object, and passes along all arguments.

        Returns:
            A :py:class:`Task` object.'''
        return Task(self, *args, **kwargs)


class Task:
    '''
    The Task class represents a single task step.  It may contain an arbitrary
    number of :py:class:`Subtask` instances whose statuses will be displayed in
    a table in slack.

    :param Notifier notifier: The top-level Notifier instance this class belongs to.
                              Should not be passed to the :py:meth:`Notifier.task` method.
    :param color color: The initial color line while the task is active.
    :type color: good, warning, or danger
    :param str title: Title of task message.
    :param str text: Body text of task message.
    :param bool status_prefix: Whether to add "Started"/"Finished" to body text automatically.
    '''

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
        '''Trigger message to be published or updated on Slack.'''
        self.message.publish()

    def subtask(self, *args, **kwargs):
        '''Create a :py:class:`Subtask` and passes all arguments to it.'''
        return Subtask(self, *args, **kwargs)

    def update(self, *args, **kwargs):
        '''Convenience method for updating the associated :py:class:`Message` instance.
        Passes all arguments to :py:meth:`Message.update`.
        '''
        self.message.update(*args, **kwargs)


class Subtask:
    '''
    Represents a subtask belonging to a specific top-level :py:class:`Task` step.
    Subtasks are either in a list or a table field inside the task message.
    '''
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


class Message:
    '''Represets a single Slack message.'''
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
        '''Updates any of the message properties.'''
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
        '''Adds a Slack attachment to the message and returns its index.'''
        self.extra.append(attachment)
        return len(self.extra) - 1

    def update_attachment(self, index, attachment):
        '''Updates a Slack attachment belonging to the message.'''
        self.extra[index] = attachment

    def publish(self):
        '''Publishes or updates an already published Slack message.
        This is the only :py:class:`Message` method that sends anything to Slack.'''
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
