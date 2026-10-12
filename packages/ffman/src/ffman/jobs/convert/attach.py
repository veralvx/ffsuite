"""The attach flow: bash's convert --add-subs -- the track added, every other stream copied."""

from pathlib import Path

from ffman.jobs.convert import covers, output, tagging
from ffman.media.paths import ext_of, file_url, read_file, resolve_output
from ffman.media.probe import read
from ffman.media.run import Runner, note
from ffman.plan.encode import container_flags
from ffman.plan.request import ConvertOptions
from ffman.plan.streams import attach_streams, attachments, kept_metadata, subtitle_codec
from ffman.subs.ingest import PASSED_THROUGH, ingest, passed
from ffman.subs.srt import srt


def run(o: ConvertOptions, runner: Runner) -> None:
    """A soft subtitle track added, nothing re-encoded (bash's attach)."""
    subs, language = o.add_subs[0], (o.languages[0] if o.languages else None)
    media = read(o.input, runner)
    target = resolve_output(o.input, o.output, in_place=o.in_place, overwrite=o.overwrite)
    out_ext = ext_of(str(target))
    _ = subtitle_codec(out_ext, "srt")  # the container takes text subtitles: before reading them
    data = read_file(subs)
    transcript = ingest(subs, data)
    for line in transcript.notes:
        note(line)
    tags = tagging.metadata_file(
        o, runner, media, out_ext
    )  # after the flow's refusals, before any pass (F6)
    codec = subtitle_codec(out_ext, transcript.fmt)  # an ASS stays styled where it can (Matroska)
    if transcript.fmt in PASSED_THROUGH:
        track = str(runner.workdir / f"subs.{transcript.fmt}")
        _ = Path(track).write_bytes(passed(data, subs).data)  # UTF-8, each NUL U+FFFD
    else:
        track = str(runner.workdir / "subs.srt")
        # each text for the track's codec; UTF-8: ffmpeg drops a cue that is not (decode.c)
        written = srt(transcript.chunks, media.duration, codec=codec)
        _ = Path(track).write_text(written, encoding="utf-8")
    n = len(media.subtitles)  # the new track's index among the subtitles
    tagged = [f"-metadata:s:s:{n}", f"language={language}"] if language else []
    maps, copied = attach_streams(ext_of(o.input), out_ext, codec, n)
    inputs = ["-i", file_url(o.input), "-i", file_url(track)]
    extra, kept = kept_metadata(inputs, tags.path)
    whole = [*maps, "-map", "1:s:0", *kept, "-c", "copy"]
    args = [*inputs, *extra, *whole, *copied, *tagged, *container_flags(out_ext)]
    labelled = tagging.tagging(runner, tagging.Given(media, o.input, tags.path), args, out_ext)
    attached = attachments(media, ext_of(o.input), out_ext)  # carried by the maps, within a family
    job = covers.Job(
        file_url(o.input),
        tuple(args),
        media.pictures,
        len(media.attachments) if attached.carry else 0,
    )
    cover = covers.kept(runner, media, out_ext, job)  # as every flow (3.15)
    for line in (
        *tags.notes,
        *cover.notes,
        *([attached.note] if attached.note else []),
        *labelled.notes,
    ):
        note(line)
    output.write(runner, target, [*args, *cover.args, *labelled.args])
