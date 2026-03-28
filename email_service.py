class EmailService:
    @staticmethod
    def send_simple_email(to_email, subject, body):
        print(f"Email sent to {to_email}: {subject}")
        return True
