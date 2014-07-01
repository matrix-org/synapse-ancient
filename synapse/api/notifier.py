
class Notifier(object):

    def __init__(self):
        pass

    def notify_user_for_messages(self, user, messages):
        """ Notifies the given user for the given messages if and only if they are online.

        Args:
            user: The user being notified
            messages: The messages they should receive.
        """
        pass

    def process_incoming_message(self, message):
        """ Checks if anyone should be notified about the given message.

        Args:
            message: The message being checked.
        """
        pass
