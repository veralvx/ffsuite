/* assdump: what libass reads of an ASS or SSA file -- the track's header, every style and every
 * event as libass holds them, and libass's own messages -- one JSON object on stdout.
 *
 * Build against libass 0.17.4 (nixpkgs' pin), static so that its internal ass_lazy_track_init
 * links (a shared libass hides it) -- from its tag, with FreeType, FriBidi, HarfBuzz and
 * Fontconfig's headers: ./autogen.sh && ./configure --prefix=$P --disable-shared --disable-asm
 * && make install; then
 * cc assdump.c $(PKG_CONFIG_PATH=$P/lib/pkgconfig pkg-config --cflags --libs --static libass) -o assdump
 * Usage: assdump FILE
 */
#include <ass/ass.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

void ass_lazy_track_init(ASS_Library *lib, ASS_Track *track); /* libass's: the PlayRes defaults */

static void json_string(const char *s)
{
    if (!s) {
        fputs("null", stdout);
        return;
    }
    putchar('"');
    for (const unsigned char *p = (const unsigned char *)s; *p; p++) {
        if (*p == '"' || *p == '\\')
            printf("\\%c", *p);
        else if (*p < 0x20)
            printf("\\u%04x", *p);
        else
            putchar(*p);
    }
    putchar('"');
}

static void message(int level, const char *fmt, va_list va, void *data)
{
    (void)data;
    if (level > 2) /* errors and warnings only (MSGL_WARN is 2) */
        return;
    vfprintf(stderr, fmt, va);
    fputc('\n', stderr);
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: assdump FILE\n");
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f)
        return 2;
    long size = fseek(f, 0, SEEK_END) ? -1 : ftell(f);
    char *data = size < 0 || fseek(f, 0, SEEK_SET) ? NULL : malloc(size + 1);
    if (!data || fread(data, 1, size, f) != (size_t)size) {
        fclose(f);
        free(data);
        return 2;
    }
    fclose(f);

    ASS_Library *lib = ass_library_init();
    ass_set_message_cb(lib, message, NULL);
    ASS_Track *t = ass_read_memory(lib, data, size, NULL);
    if (!t) {
        puts("null");
        ass_library_done(lib);
        free(data);
        return 0;
    }
    ass_lazy_track_init(lib, t);

    printf("{\"type\": \"%s\", \"PlayResX\": %d, \"PlayResY\": %d, \"LayoutResX\": %d, "
           "\"LayoutResY\": %d, \"WrapStyle\": %d, \"ScaledBorderAndShadow\": %d, "
           "\"Kerning\": %d, \"YCbCrMatrix\": %d, \"Timer\": %g, \"Language\": ",
           t->track_type == TRACK_TYPE_ASS ? "ASS" : t->track_type == TRACK_TYPE_SSA ? "SSA" : "?",
           t->PlayResX, t->PlayResY, t->LayoutResX, t->LayoutResY, t->WrapStyle,
           t->ScaledBorderAndShadow, t->Kerning, (int)t->YCbCrMatrix, t->Timer);
    json_string(t->Language);
    printf(", \"default_style\": %d, \"styles\": [", t->default_style);
    for (int i = 0; i < t->n_styles; i++) {
        const ASS_Style *s = &t->styles[i];
        printf("%s{\"Name\": ", i ? ", " : "");
        json_string(s->Name);
        printf(", \"FontName\": ");
        json_string(s->FontName);
        printf(", \"FontSize\": %g, \"Primary\": \"%08X\", \"Secondary\": \"%08X\", "
               "\"Outline\": \"%08X\", \"Back\": \"%08X\", \"Bold\": %d, \"Italic\": %d, "
               "\"Underline\": %d, \"StrikeOut\": %d, \"ScaleX\": %g, \"ScaleY\": %g, "
               "\"Spacing\": %g, \"Angle\": %g, \"BorderStyle\": %d, \"OutlineWidth\": %g, "
               "\"Shadow\": %g, \"Alignment\": %d, \"MarginL\": %d, \"MarginR\": %d, "
               "\"MarginV\": %d, \"Encoding\": %d}",
               s->FontSize, s->PrimaryColour, s->SecondaryColour, s->OutlineColour,
               s->BackColour, s->Bold, s->Italic, s->Underline, s->StrikeOut, s->ScaleX,
               s->ScaleY, s->Spacing, s->Angle, s->BorderStyle, s->Outline, s->Shadow,
               s->Alignment, s->MarginL, s->MarginR, s->MarginV, s->Encoding);
    }
    printf("], \"events\": [");
    for (int i = 0; i < t->n_events; i++) {
        const ASS_Event *e = &t->events[i];
        printf("%s{\"Start\": %lld, \"Duration\": %lld, \"Layer\": %d, \"Style\": ", i ? ", " : "",
               e->Start, e->Duration, e->Layer);
        json_string(t->styles[e->Style].Name);
        printf(", \"StyleIndex\": %d, \"Name\": ", e->Style);
        json_string(e->Name);
        printf(", \"MarginL\": %d, \"MarginR\": %d, \"MarginV\": %d, \"Effect\": ", e->MarginL,
               e->MarginR, e->MarginV);
        json_string(e->Effect);
        printf(", \"Text\": ");
        json_string(e->Text);
        putchar('}');
    }
    puts("]}");
    ass_free_track(t);
    ass_library_done(lib);
    free(data);
    return 0;
}
