import reflex as rx

from app.components.dashboard import dashboard_header
from app.components.short_creator import creator_select
from app.services.ad_generation import PRODUCT_STYLES, UGC_STYLES, PLATFORMS
from app.states.ad_state import AdState, StoryboardScene


def ad_field(
    label: str, name: str, placeholder: str, maximum: int, required: bool = True
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            label,
            html_for=name,
            class_name="mb-2 block text-xs font-medium text-white/70",
        ),
        rx.el.textarea(
            id=name,
            name=name,
            required=required,
            max_length=maximum,
            default_value=AdState.brief[name],
            key=AdState.brief[name],
            placeholder=placeholder,
            class_name="min-h-20 w-full resize-y rounded-xl border border-white/15 bg-[#0B0B10] px-4 py-3 text-sm leading-relaxed text-white placeholder:text-white/30 focus:border-violet-400 focus:outline-hidden focus:ring-2 focus:ring-violet-400/20",
        ),
        class_name="w-full",
    )


def photo_upload() -> rx.Component:
    return rx.el.section(
        rx.el.h2(
            "1. Your product photo",
            class_name="text-lg font-semibold text-white",
        ),
        rx.el.p(
            "Upload a photo you have permission to use. PNG, JPEG or WebP · up to 8 MB · max 8 megapixels. Photos are decoded and metadata removed; stored copies may be resized to 1600px.",
            class_name="mt-2 text-xs leading-relaxed text-white/45",
        ),
        rx.upload.root(
            rx.icon("image-plus", class_name="mx-auto h-7 w-7 text-[#A78BFA]"),
            rx.el.p(
                "Choose a product photo",
                class_name="mt-3 text-sm font-medium text-white/75",
            ),
            rx.el.p(
                "Click or drop one image here",
                class_name="mt-2 text-xs text-white/45",
            ),
            id="ad-photo",
            multiple=False,
            max_files=1,
            max_size=8 * 1024 * 1024,
            accept={
                "image/png": [".png"],
                "image/jpeg": [".jpg", ".jpeg"],
                "image/webp": [".webp"],
            },
            disabled=AdState.busy | AdState.uploading | AdState.loading,
            class_name="mt-5 cursor-pointer rounded-2xl border border-dashed border-violet-400/30 bg-[#0B0B10] p-6 text-center focus-visible:outline-2 focus-visible:outline-violet-400",
        ),
        rx.el.div(
            rx.foreach(
                rx.selected_files("ad-photo"),
                lambda name: rx.el.p(
                    name, class_name="break-all text-xs text-white/60"
                ),
            ),
            class_name="mt-3",
        ),
        rx.el.button(
            rx.icon("upload", class_name="h-4 w-4"),
            rx.cond(
                AdState.uploading,
                "Validating photo…",
                rx.cond(
                    AdState.photo_file != "",
                    "Upload replacement photo",
                    "Upload selected photo",
                ),
            ),
            type="button",
            on_click=AdState.upload_photo(
                rx.upload_files(upload_id="ad-photo")
            ),
            disabled=AdState.busy | AdState.uploading | AdState.loading,
            class_name="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-sm text-white/80 hover:bg-white/10 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
        ),
        rx.cond(
            AdState.photo_file != "",
            rx.el.figure(
                rx.el.img(
                    src=rx.get_upload_url(AdState.photo_file),
                    alt="Your uploaded product photo",
                    class_name="mx-auto mt-5 max-h-56 w-full rounded-xl bg-[#0B0B10] object-contain",
                ),
                rx.el.figcaption(
                    "Your upload · not an AI-generated image",
                    class_name="mt-2 text-center text-xs text-[#448BFF]",
                ),
            ),
        ),
        rx.el.p(
            "Image links are shareable. Do not upload sensitive information. Local photo storage may be cleared on redeployment; project text is saved separately.",
            class_name="mt-4 text-xs leading-relaxed text-white/40",
        ),
        class_name="rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
    )


def ad_form() -> rx.Component:
    return rx.el.form(
        rx.el.h2(
            "2. Build an honest ad brief",
            class_name="mb-5 text-lg font-semibold text-white",
        ),
        rx.el.fieldset(
            ad_field(
                "Product name",
                "product_name",
                "For example: Foldaway Desk Stand",
                150,
            ),
            ad_field(
                "Product description",
                "description",
                "What is it? Include materials, features and what is actually included.",
                1200,
            ),
            ad_field(
                "Target audience",
                "audience",
                "Who is it for, and in what context?",
                400,
            ),
            ad_field(
                "User problem",
                "problem",
                "The practical frustration your product addresses.",
                500,
            ),
            ad_field(
                "Main benefit",
                "benefit",
                "A specific, supportable benefit — not a promise of guaranteed results.",
                500,
            ),
            ad_field(
                "Voice / tone",
                "tone",
                "For example: friendly, clear and practical; no hype.",
                200,
            ),
            ad_field(
                "Call to action",
                "cta",
                "For example: Explore the available sizes.",
                200,
            ),
            ad_field(
                "Supported product facts / claims",
                "claims",
                "Only facts you can substantiate. Describe observable features or a demonstration; no invented reviews or results.",
                1200,
            ),
            rx.el.p(
                "User-supplied claims are not independently verified. The AI will omit unsupported promises and flag uncertainties. Review the draft before publishing.",
                class_name="text-xs leading-relaxed text-[#448BFF]",
            ),
            rx.cond(
                AdState.kind == "ugc_ad",
                rx.el.div(
                    rx.el.h3(
                        "Creator-style direction",
                        class_name="text-base font-semibold text-[#C4B5FD]",
                    ),
                    ad_field(
                        "Proposed creator persona",
                        "persona",
                        "For example: a practical home-organising presenter. Not a real customer endorsement.",
                        400,
                    ),
                    ad_field(
                        "Authentic filming situation",
                        "situation",
                        "For example: a handheld shot at a kitchen counter in natural light.",
                        500,
                    ),
                    ad_field(
                        "Demonstration / use",
                        "demonstration",
                        "What can the presenter visibly demonstrate without inventing results?",
                        600,
                    ),
                    ad_field(
                        "Conversational direction / objection",
                        "objection",
                        "Which realistic question or hesitation should the demo address?",
                        400,
                    ),
                    rx.el.p(
                        "UGC here means a creator-style script, not user-generated testimonials. No invented first-person experiences, reviews, endorsements or avatar footage.",
                        class_name="text-xs leading-relaxed text-white/50",
                    ),
                    class_name="flex flex-col gap-5 rounded-2xl border border-violet-400/20 bg-violet-500/5 p-4",
                ),
            ),
            ad_field(
                "Price / offer (optional)",
                "offer",
                "Only a current, accurate price or offer. Leave blank if not relevant.",
                500,
                False,
            ),
            ad_field(
                "Product URL (optional, public HTTPS)",
                "url",
                "https://example.com/product — stored as text only, never fetched.",
                500,
                False,
            ),
            creator_select(
                "Platform", "platform", PLATFORMS, AdState.brief["platform"]
            ),
            creator_select(
                "Target script duration (seconds)",
                "duration",
                ["15", "30", "45", "60"],
                AdState.brief["duration"],
            ),
            rx.cond(
                AdState.kind == "ugc_ad",
                creator_select(
                    "Visual direction",
                    "style",
                    UGC_STYLES,
                    AdState.brief["style"],
                ),
                creator_select(
                    "Visual direction",
                    "style",
                    PRODUCT_STYLES,
                    AdState.brief["style"],
                ),
            ),
            disabled=AdState.busy | AdState.uploading | AdState.loading,
            class_name="flex min-w-0 flex-col gap-5 disabled:opacity-60",
        ),
        rx.el.button(
            rx.cond(
                AdState.busy,
                rx.icon("loader-circle", class_name="h-4 w-4 animate-spin"),
                rx.icon("sparkles", class_name="h-4 w-4"),
            ),
            rx.cond(
                AdState.busy,
                "Writing your draft…",
                "Save brief & generate script · Free",
            ),
            type="submit",
            disabled=AdState.busy
            | AdState.uploading
            | AdState.loading
            | (AdState.photo_file == ""),
            class_name="mt-7 flex w-full items-center justify-center gap-2 rounded-xl bg-[#8B5CF6] px-5 py-4 text-sm font-semibold text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
        ),
        rx.el.p(
            "Script/storyboard drafts use no video credits. Each submission saves a new draft; your previous projects are kept. Keep this tab open while writing (about a minute).",
            class_name="mt-3 text-center text-xs leading-relaxed text-white/45",
        ),
        on_submit=AdState.submit,
        class_name="rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
    )


def ad_feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            AdState.loading,
            rx.el.p(
                "Loading your saved creator workspace…",
                role="status",
                class_name="mt-5 animate-pulse rounded-2xl bg-white/5 p-5 text-sm text-white/60",
            ),
        ),
        rx.cond(
            AdState.error != "",
            rx.el.p(
                AdState.error,
                role="alert",
                class_name="mt-5 rounded-2xl border border-red-400/20 bg-red-500/10 p-5 text-sm leading-relaxed text-red-200",
            ),
        ),
        rx.cond(
            AdState.notice != "",
            rx.el.p(
                AdState.notice,
                role="status",
                class_name="mt-5 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-5 text-sm leading-relaxed text-white/70",
            ),
        ),
        rx.cond(
            AdState.busy | AdState.uploading,
            rx.el.section(
                rx.el.div(
                    rx.icon(
                        "loader-circle",
                        class_name="h-5 w-5 animate-spin text-[#C4B5FD]",
                    ),
                    rx.el.p(AdState.stage, class_name="text-sm text-white/80"),
                    class_name="flex items-center gap-3",
                ),
                rx.cond(
                    AdState.busy,
                    rx.el.progress(
                        value=AdState.progress,
                        max=100,
                        aria_label="Ad draft progress",
                        class_name="mt-4 h-2 w-full accent-[#8B5CF6]",
                    ),
                ),
                role="status",
                aria_live="polite",
                class_name="mt-5 rounded-2xl border border-violet-400/20 bg-violet-500/5 p-5",
            ),
        ),
    )


def scene_card(scene: StoryboardScene) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.span(
                scene["purpose"].upper(),
                class_name="text-xs font-semibold tracking-wider text-[#A78BFA]",
            ),
            rx.el.span(
                f"{scene['start']:.1f}–{scene['end']:.1f}s",
                class_name="text-xs text-white/45",
            ),
            class_name="flex justify-between gap-3",
        ),
        rx.el.h3(
            "Suggested filming direction",
            class_name="mt-4 text-xs font-semibold text-[#448BFF]",
        ),
        rx.el.p(
            scene["visual"],
            class_name="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-white/70",
        ),
        rx.el.h3(
            "Script segment",
            class_name="mt-5 text-xs font-semibold text-white/50",
        ),
        rx.el.p(
            scene["narration"],
            class_name="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-white/80",
        ),
        class_name="min-w-0 rounded-2xl border border-white/8 bg-[#0B0B10] p-5",
    )


def ad_result() -> rx.Component:
    return rx.cond(
        AdState.title != "",
        rx.el.section(
            rx.el.span(
                "SAVED AD DRAFT · NO RENDERED VIDEO",
                class_name="text-[10px] font-semibold tracking-wider text-[#448BFF]",
            ),
            rx.el.h2(
                AdState.title,
                class_name="mt-3 break-words text-2xl font-semibold text-white",
            ),
            rx.el.p(
                "No MP4, recorded voice, generated scene image or avatar footage has been produced. Avatar video is unavailable until a real provider is connected. Timings below are script estimates, not recorded media.",
                class_name="mt-3 text-sm leading-relaxed text-white/50",
            ),
            rx.cond(
                AdState.photo_file != "",
                rx.el.figure(
                    rx.el.img(
                        src=rx.get_upload_url(AdState.photo_file),
                        alt="Uploaded product photo associated with this draft",
                        class_name="mt-5 max-h-64 w-full rounded-xl bg-[#0B0B10] object-contain",
                    ),
                    rx.el.figcaption(
                        "Original user-uploaded product photo (sanitised copy) · not AI-generated",
                        class_name="mt-2 text-xs text-[#448BFF]",
                    ),
                ),
            ),
            rx.cond(
                AdState.script != "",
                rx.el.div(
                    rx.el.h3(
                        "Ad script / proposed voiceover text",
                        class_name="mt-6 text-lg font-semibold text-white",
                    ),
                    rx.el.p(
                        AdState.script,
                        class_name="mt-3 whitespace-pre-wrap text-base leading-relaxed text-white/80",
                    ),
                    rx.el.h3(
                        "Storyboard · suggested shots",
                        class_name="mt-7 text-lg font-semibold text-white",
                    ),
                    rx.el.div(
                        rx.foreach(AdState.scenes, scene_card),
                        class_name="mt-4 grid w-full grid-cols-1 gap-4 md:grid-cols-2",
                    ),
                    rx.el.h3(
                        "Image grounding",
                        class_name="mt-6 text-sm font-semibold text-[#448BFF]",
                    ),
                    rx.el.p(
                        AdState.observations,
                        class_name="mt-2 text-sm leading-relaxed text-white/65",
                    ),
                    rx.el.h3(
                        "Claim review notes",
                        class_name="mt-5 text-sm font-semibold text-[#C4B5FD]",
                    ),
                    rx.el.p(
                        AdState.claim_notes,
                        class_name="mt-2 text-sm leading-relaxed text-white/65",
                    ),
                    rx.cond(
                        AdState.captions_display != "",
                        rx.el.details(
                            rx.el.summary(
                                "Proposed captions · estimated timing",
                                class_name="mt-5 cursor-pointer text-sm text-[#C4B5FD]",
                            ),
                            rx.el.p(
                                AdState.captions_display,
                                class_name="mt-3 whitespace-pre-wrap text-xs leading-relaxed text-white/60",
                            ),
                        ),
                    ),
                ),
            ),
            rx.el.a(
                "Open saved draft",
                href=f"/ads/{AdState.project_id}",
                class_name="mt-6 inline-block rounded-xl bg-violet-500/10 px-4 py-3 text-sm text-[#C4B5FD] hover:bg-violet-500/20",
            ),
            rx.el.a(
                "My Videos · manage saved text",
                href="/videos",
                class_name="ml-4 mt-4 inline-block text-sm text-white/60 hover:text-white",
            ),
            class_name="mt-8 w-full rounded-3xl border border-violet-400/20 bg-[#13131C] p-5 sm:p-7",
        ),
    )


def ad_creator() -> rx.Component:
    return rx.el.main(
        dashboard_header(),
        rx.el.div(
            rx.el.a(
                "← Dashboard",
                href="/",
                class_name="text-xs text-white/50 hover:text-white",
            ),
            rx.el.p(
                "YOUR PRODUCT. AN HONEST STORY.",
                class_name="mt-7 text-[10px] font-semibold tracking-[0.18em] text-[#A78BFA]",
            ),
            rx.el.h1(
                rx.cond(
                    AdState.kind == "ugc_ad",
                    "Create a UGC Ad",
                    "Create a Product Ad",
                ),
                class_name="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl",
            ),
            rx.el.p(
                rx.cond(
                    AdState.kind == "ugc_ad",
                    "A conversational hook, practical demonstration and clear CTA — a proposed creator-style script, never a fabricated customer testimonial.",
                    "Turn a genuine product photo and clear brief into a benefit-led hook, observable proof and a strong CTA.",
                ),
                class_name="mt-4 text-sm leading-relaxed text-white/55",
            ),
            rx.el.p(
                "Free script & storyboard drafts · no video credits reserved or charged · no MP4 or avatar rendered",
                class_name="mt-4 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-4 text-xs leading-relaxed text-[#448BFF]",
            ),
            ad_feedback(),
            rx.el.div(
                photo_upload(),
                ad_form(),
                class_name="mx-auto mt-7 flex w-full max-w-2xl flex-col gap-6",
            ),
            ad_result(),
            class_name="mx-auto w-full max-w-5xl flex-1 px-5 py-8 sm:px-8 sm:py-10",
        ),
        class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
    )


def ad_detail() -> rx.Component:
    return rx.el.main(
        dashboard_header(),
        rx.el.div(
            rx.el.a(
                "← My Videos",
                href="/videos",
                class_name="text-xs text-white/50 hover:text-white",
            ),
            rx.el.h1(
                "Saved ad draft",
                class_name="mt-7 text-3xl font-semibold text-white",
            ),
            ad_feedback(),
            rx.cond(
                AdState.title != "",
                rx.el.p(
                    AdState.detail_status,
                    role="status",
                    class_name="mt-5 text-sm text-[#448BFF]",
                ),
            ),
            ad_result(),
            rx.cond(
                AdState.brief_display.length() > 0,
                rx.el.details(
                    rx.el.summary(
                        "View the saved brief",
                        class_name="mt-7 cursor-pointer text-base font-semibold text-[#C4B5FD]",
                    ),
                    rx.el.dl(
                        rx.foreach(
                            AdState.brief_display,
                            lambda item: rx.el.div(
                                rx.el.dt(
                                    item["label"],
                                    class_name="text-xs font-semibold text-white/50",
                                ),
                                rx.el.dd(
                                    item["value"],
                                    class_name="mt-2 break-words whitespace-pre-wrap text-sm leading-relaxed text-white/75",
                                ),
                                class_name="border-b border-white/8 py-4",
                            ),
                        ),
                        class_name="mt-4 rounded-2xl bg-[#13131C] px-5",
                    ),
                ),
            ),
            class_name="mx-auto w-full max-w-5xl flex-1 px-5 py-8 sm:px-8",
        ),
        class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
    )
