from django.core.management.base import BaseCommand
from lmsApp.tasks import (
    send_deadline_reminders,
    send_post_completion_followups,
    send_monthly_platform_report,
    sync_microsoft_learn_catalog,
)


class Command(BaseCommand):
    help = "Manually execute or test scheduled LMS Celery tasks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--task",
            type=str,
            choices=[
                "deadline_reminders",
                "completion_followups",
                "platform_report",
                "sync_ms_learn",
                "all",
            ],
            default="all",
            help="Specify which scheduled task to run (default: all)",
        )
        parser.add_argument(
            "--async-mode",
            action="store_true",
            help="Dispatch to Celery queue via .delay() instead of running synchronously.",
        )

    def handle(self, *args, **options):
        selected_task = options["task"]
        async_mode = options["async_mode"]

        tasks_to_run = []

        if selected_task in ("deadline_reminders", "all"):
            tasks_to_run.append(
                (
                    "Deadline Reminders",
                    send_deadline_reminders,
                    [],
                    {},
                )
            )

        if selected_task in ("completion_followups", "all"):
            tasks_to_run.append(
                (
                    "Post-Completion Follow-ups",
                    send_post_completion_followups,
                    [],
                    {},
                )
            )

        if selected_task in ("platform_report", "all"):
            tasks_to_run.append(
                (
                    "Monthly Platform Report",
                    send_monthly_platform_report,
                    [],
                    {},
                )
            )

        if selected_task in ("sync_ms_learn", "all"):
            tasks_to_run.append(
                (
                    "Microsoft Learn Catalog Sync",
                    sync_microsoft_learn_catalog,
                    [],
                    {
                        "products": ["azure", "m365", "security", "entra"],
                        "roles": ["administrator"],
                    },
                )
            )

        for name, func, task_args, task_kwargs in tasks_to_run:
            self.stdout.write(f"\n--- Running: {name} ---")

            if async_mode:
                # Dispatches task to Celery worker queue
                result = func.delay(*task_args, **task_kwargs)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Dispatched {name} to Celery queue (Task ID: {result.id})"
                    )
                )
            else:
                # Runs function synchronously in foreground terminal
                try:
                    result = func(*task_args, **task_kwargs)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully completed {name}.\nResult: {result}"
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed running {name}.\nError: {e}"
                        )
                    )