import reflex as rx
import reflex_enterprise as rxe
import logging

from reflex_enterprise.auth import User
from sqlalchemy import text
from app.services.usage import FREE_VIDEO_LIMIT
from app.services.analytics import append_event


class OnboardingState(rx.State):
    step: int = 0
    completed: bool = False
    loading: bool = True
    saving: bool = False
    error: str = ""
    ready: bool = False
    home: bool = False

    @rxe.event
    async def load_profile(self, home: bool = False):
        self.loading = True
        self.ready = False
        self.error = ""
        self.step = 0
        self.completed = False
        self.home = home
        yield
        try:
            user = await User.current() or {}
            subject = user.get("sub")
            if not isinstance(subject, str) or not subject.strip():
                self.error = "Your sign-in could not be confirmed. Please sign out and sign in again."
                return
            async with rx.asession() as session:
                inserted = (
                    await session.execute(
                        text("""
                    INSERT INTO creator_profiles (identity_subject, display_name, onboarding_answers, plan, monthly_video_allowance)
                    VALUES (:subject, :name, '{}'::jsonb, 'free', :allowance)
                    ON CONFLICT (identity_subject) DO NOTHING RETURNING identity_subject
                """),
                        {
                            "subject": subject,
                            "name": str(user.get("name") or "")[:200],
                            "allowance": FREE_VIDEO_LIMIT,
                        },
                    )
                ).one_or_none()
                if inserted is not None:
                    await append_event(session, "signup")
                row = (
                    await session.execute(
                        text("""
INSERT INTO creator_profiles (identity_subject, display_name, onboarding_answers, plan, monthly_video_allowance)
                    VALUES (:subject, :name, '{}', 'free', :allowance)
                    ON CONFLICT (identity_subject) DO UPDATE
                    SET display_name = EXCLUDED.display_name
                    RETURNING COALESCE(onboarding_step, 0), onboarding_completed
                """),
                        {
                            "subject": subject,
                            "allowance": FREE_VIDEO_LIMIT,
                            "name": str(user.get("name") or "")[:200],
                        },
                    )
                ).one()
                await session.commit()
            self.step = min(max(int(row[0]), 0), 3)
            self.completed = bool(row[1])
            self.ready = True
            if home and not self.completed:
                yield rx.redirect("/onboarding")
            elif not home and self.completed:
                yield rx.redirect("/")
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "We couldn't load your progress. Please try again."
        finally:
            self.loading = False

    @rxe.event
    def retry(self):
        return OnboardingState.load_profile(self.home)

    @rxe.event
    async def move(self, direction: int):
        if direction not in (-1, 1) or self.saving or not self.ready:
            return
        self.saving = True
        self.error = ""
        yield
        target = ""
        try:
            user = await User.current() or {}
            subject = user.get("sub")
            if not isinstance(subject, str) or not subject.strip():
                self.ready = False
                self.error = "Your sign-in could not be confirmed. Please sign out and sign in again."
                return
            async with rx.asession() as session:
                row = (
                    await session.execute(
                        text("""
                    SELECT COALESCE(onboarding_step, 0), onboarding_completed
                    FROM creator_profiles WHERE identity_subject = :subject
                    LIMIT 1 FOR UPDATE
                """),
                        {"subject": subject},
                    )
                ).first()
                if row is None:
                    self.ready = False
                    self.error = "Your profile couldn't be found. Reload your progress to continue."
                    return
                if row[1]:
                    new_step = 4
                    done = True
                    target = "/"
                else:
                    new_step = min(max(int(row[0]) + direction, 0), 4)
                    done = new_step == 4
                    await session.execute(
                        text("""
                        UPDATE creator_profiles
                        SET onboarding_step = :step,
                            onboarding_completed = :done,
                            onboarding_completed_at = CASE WHEN :done THEN CURRENT_TIMESTAMP ELSE onboarding_completed_at END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE identity_subject = :subject
                    """),
                        {"step": new_step, "done": done, "subject": subject},
                    )
                    target = "/create" if done else ""
                await session.commit()
            self.step = min(new_step, 3)
            self.completed = done
            if target:
                yield rx.redirect(target)
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "We couldn't save your progress. Your last saved step is safe. Please try again."
        finally:
            self.saving = False
