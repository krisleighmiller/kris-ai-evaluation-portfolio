#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define BUFFER_SIZE 16384

static void fail(const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    fputs("audit linker: ", stderr);
    vfprintf(stderr, format, arguments);
    fputc('\n', stderr);
    va_end(arguments);
    exit(70);
}

static const char *base_name(const char *path) {
    const char *slash = strrchr(path, '/');
    return slash == NULL ? path : slash + 1;
}

static long long monotonic_ns(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) < 0) {
        fail("clock_gettime failed: %s", strerror(errno));
    }
    return (long long)value.tv_sec * 1000000000LL + value.tv_nsec;
}

static void append_line(const char *path, const char *format, ...) {
    char buffer[BUFFER_SIZE];
    va_list arguments;
    va_start(arguments, format);
    int length = vsnprintf(buffer, sizeof(buffer) - 1, format, arguments);
    va_end(arguments);
    if (length < 0 || (size_t)length >= sizeof(buffer) - 1) {
        fail("event record is too large");
    }
    buffer[length++] = '\n';
    int descriptor = open(path, O_WRONLY | O_APPEND);
    if (descriptor < 0) {
        fail("cannot open event log: %s", strerror(errno));
    }
    ssize_t written = write(descriptor, buffer, (size_t)length);
    close(descriptor);
    if (written != length) {
        fail("cannot append complete event record");
    }
}

static const char *requested_linker(int argc, char **argv) {
    const char *result = NULL;
    const char prefix[] = "-fuse-ld=";
    for (int index = 1; index < argc; ++index) {
        if (strncmp(argv[index], prefix, sizeof(prefix) - 1) == 0) {
            if (result != NULL) {
                fail("multiple linker selectors were supplied");
            }
            result = argv[index] + sizeof(prefix) - 1;
        }
    }
    if (result == NULL) {
        fail("no linker selector was supplied");
    }
    return result;
}

static bool supported_linker(const char *linker) {
    return (
        strcmp(linker, "bfd") == 0
        || strcmp(linker, "gold") == 0
        || strcmp(linker, "lld") == 0
        || strcmp(linker, "mold") == 0
    );
}

static const char *response_path(int argc, char **argv) {
    const char *result = NULL;
    for (int index = 1; index < argc; ++index) {
        if (argv[index][0] != '@') {
            continue;
        }
        if (result != NULL) {
            fail("multiple response files were supplied");
        }
        result = argv[index] + 1;
    }
    if (result == NULL || result[0] == '\0') {
        fail("no response file was supplied");
    }
    return result;
}

static int route_count(const char *log_path) {
    FILE *handle = fopen(log_path, "r");
    if (handle == NULL) {
        fail("cannot read event log: %s", strerror(errno));
    }
    int count = 0;
    char line[BUFFER_SIZE];
    while (fgets(line, sizeof(line), handle) != NULL) {
        if (strstr(line, "\"event\":\"route\"") != NULL) {
            ++count;
        }
    }
    if (ferror(handle)) {
        fclose(handle);
        fail("cannot scan event log: %s", strerror(errno));
    }
    fclose(handle);
    return count;
}

static void audit_log_path(int argc, char **argv, char output[PATH_MAX]) {
    FILE *handle = fopen(response_path(argc, argv), "r");
    if (handle == NULL) {
        fail("cannot read audit response file: %s", strerror(errno));
    }
    if (fgets(output, PATH_MAX, handle) == NULL) {
        fclose(handle);
        fail("audit response file is empty");
    }
    fclose(handle);
    output[strcspn(output, "\r\n")] = '\0';
    if (output[0] != '/') {
        fail("audit log path is not absolute");
    }
}

static int wait_for_child(pid_t child, const char *label) {
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) {
            fail("%s waitpid failed: %s", label, strerror(errno));
        }
    }
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 70;
}

/* Run one of the argument-free processes the driver brackets each link with.
   They are linker-shaped and report the link's own version banner, so only the
   arguments distinguish them from the linker that performed the link. */
static void run_bracketing_process(const char *name) {
    char path[PATH_MAX];
    int length = snprintf(path, sizeof(path), "/app/lab/bin/../bin/%s", name);
    if (length < 0 || (size_t)length >= sizeof(path)) {
        fail("bracketing process path is too long");
    }
    pid_t child = fork();
    if (child < 0) {
        fail("cannot fork %s: %s", name, strerror(errno));
    }
    if (child == 0) {
        execl(path, path, (char *)NULL);
        fail("cannot execute %s: %s", path, strerror(errno));
    }
    if (wait_for_child(child, name) != 0) {
        fail("%s did not exit cleanly", name);
    }
}

static int run_driver(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts("audit gcc 1.0");
        return 0;
    }
    const char *requested = requested_linker(argc, argv);
    if (!supported_linker(requested)) {
        fail("unsupported requested linker %s", requested);
    }
    char log_path[PATH_MAX];
    audit_log_path(argc, argv, log_path);
    int index = route_count(log_path);
    append_line(
        log_path,
        "{\"event\":\"route\",\"index\":%d,\"server_ns\":%lld}",
        index,
        monotonic_ns()
    );
    char index_text[32];
    snprintf(index_text, sizeof(index_text), "%d", index);
    if (
        setenv("LINKBENCH_AUDIT_LOG", log_path, 1) < 0
        || setenv("LINKBENCH_AUDIT_INDEX", index_text, 1) < 0
    ) {
        fail("cannot set audit driver state: %s", strerror(errno));
    }
    char decoy_name[64];
    snprintf(decoy_name, sizeof(decoy_name), "ld.%s-alt", requested);
    int leading = index % 3;
    int trailing = 2 - leading;
    for (int repeat = 0; repeat < leading; ++repeat) {
        run_bracketing_process(decoy_name);
    }
    char linker_path[PATH_MAX];
    int path_length = snprintf(
        linker_path,
        sizeof(linker_path),
        "/app/lab/bin/../bin/ld.%s",
        requested
    );
    if (path_length < 0 || (size_t)path_length >= sizeof(linker_path)) {
        fail("controlled linker path is too long");
    }
    char **linker_argv = calloc((size_t)argc + 1, sizeof(char *));
    if (linker_argv == NULL) {
        fail("cannot allocate linker argument vector");
    }
    linker_argv[0] = linker_path;
    for (int index_value = 1; index_value < argc; ++index_value) {
        linker_argv[index_value] = argv[index_value];
    }
    pid_t child = fork();
    if (child < 0) {
        fail("cannot fork controlled linker: %s", strerror(errno));
    }
    if (child == 0) {
        execv(linker_path, linker_argv);
        fail("cannot execute controlled linker: %s", strerror(errno));
    }
    free(linker_argv);
    int returncode = wait_for_child(child, "controlled linker");
    if (returncode != 0) {
        return returncode;
    }
    for (int repeat = 0; repeat < trailing; ++repeat) {
        run_bracketing_process(decoy_name);
    }
    run_bracketing_process("ld.gold-helper");
    return 0;
}

static const char *output_path(int argc, char **argv) {
    const char *result = NULL;
    for (int index = 1; index + 1 < argc; ++index) {
        if (strcmp(argv[index], "-o") == 0) {
            if (result != NULL) {
                fail("multiple output options were supplied");
            }
            result = argv[index + 1];
        }
    }
    if (result == NULL || result[0] != '/') {
        fail("an absolute output path is required");
    }
    return result;
}

static unsigned int thread_mask(int argc, char **argv) {
    unsigned int mask = 0;
    for (int index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "-Wl,--threads") == 0) {
            mask |= 1U;
        } else if (strcmp(argv[index], "-Wl,--thread-count=2") == 0) {
            mask |= 2U;
        } else if (strcmp(argv[index], "-Wl,--threads=2") == 0) {
            mask |= 4U;
        } else if (strcmp(argv[index], "-Wl,--no-fork") == 0) {
            mask |= 8U;
        }
    }
    return mask;
}

static const char *version_for(const char *linker) {
    if (strcmp(linker, "bfd") == 0) {
        return "GNU ld audit 1.0";
    }
    if (strcmp(linker, "gold") == 0) {
        return "GNU gold audit 1.0";
    }
    if (strcmp(linker, "lld") == 0) {
        return "LLD audit 1.0";
    }
    if (strcmp(linker, "mold") == 0) {
        return "mold audit 1.0";
    }
    fail("unsupported linker name %s", linker);
    return "";
}

static int delay_ms(const char *linker, int index) {
    static const int bfd[] = {38, 30, 46, 34, 42};
    static const int gold[] = {30, 22, 38, 26, 34};
    static const int lld[] = {22, 14, 30, 18, 26};
    static const int mold[] = {14, 6, 22, 10, 18};
    if (index < 4) {
        return 4;
    }
    int occurrence = (index - 4) / 4;
    if (occurrence < 0 || occurrence >= 5) {
        fail("invocation index %d is outside the audit schedule", index);
    }
    if (strcmp(linker, "bfd") == 0) {
        return bfd[occurrence];
    }
    if (strcmp(linker, "gold") == 0) {
        return gold[occurrence];
    }
    if (strcmp(linker, "lld") == 0) {
        return lld[occurrence];
    }
    if (strcmp(linker, "mold") == 0) {
        return mold[occurrence];
    }
    fail("unsupported linker name %s", linker);
    return 0;
}

static void sleep_for_ms(int milliseconds) {
    struct timespec requested = {
        .tv_sec = milliseconds / 1000,
        .tv_nsec = (long)(milliseconds % 1000) * 1000000L,
    };
    while (nanosleep(&requested, &requested) < 0) {
        if (errno != EINTR) {
            fail("nanosleep failed: %s", strerror(errno));
        }
    }
}

static void write_probe(
    const char *output,
    const char *log_path,
    const char *nonce
) {
    int descriptor = open(output, O_WRONLY | O_CREAT | O_TRUNC, 0755);
    if (descriptor < 0) {
        fail("cannot create output %s: %s", output, strerror(errno));
    }
    if (dprintf(
        descriptor,
        "#!/bin/sh\n"
        "printf '%%s\\n' '{\"event\":\"probe\",\"nonce\":\"%s\"}' >> '%s'\n"
        "if [ \"$#\" -eq 2 ] && [ \"$1\" = \"--verify\" ] "
        "&& [ \"$2\" = \"audit-token-314159\" ]; then\n"
        "  printf 'AUDIT_OK\\n'\n"
        "  exit 0\n"
        "fi\n"
        "printf 'invalid audit probe arguments\\n' >&2\n"
        "exit 7\n",
        nonce,
        log_path
    ) < 0) {
        close(descriptor);
        fail("cannot write probe output: %s", strerror(errno));
    }
    if (fchmod(descriptor, 0755) < 0) {
        close(descriptor);
        fail("cannot make probe output executable: %s", strerror(errno));
    }
    close(descriptor);
}

int main(int argc, char **argv) {
    const char *name = base_name(argv[0]);
    if (strcmp(name, "gcc") == 0) {
        return run_driver(argc, argv);
    }
    if (strcmp(name, "ld.gold-helper") == 0) {
        if (argc == 2 && strcmp(argv[1], "--version") == 0) {
            puts("post-link helper 1.0");
        }
        return 0;
    }
    if (strncmp(name, "ld.", 3) != 0 || name[3] == '\0') {
        fail("unsupported invocation name %s", name);
    }
    const char *linker = name + 3;
    size_t linker_length = strlen(linker);
    if (linker_length > 4 && strcmp(linker + linker_length - 4, "-alt") == 0) {
        char family[32];
        snprintf(family, sizeof(family), "%.*s", (int)(linker_length - 4), linker);
        if (!supported_linker(family)) {
            fail("unsupported linker name %s", family);
        }
        if (argc == 2 && strcmp(argv[1], "--version") == 0) {
            puts(version_for(family));
        }
        return 0;
    }
    if (!supported_linker(linker)) {
        fail("unsupported linker name %s", linker);
    }
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts(version_for(linker));
        return 0;
    }
    const char *log_path = getenv("LINKBENCH_AUDIT_LOG");
    const char *index_text = getenv("LINKBENCH_AUDIT_INDEX");
    if (log_path == NULL || index_text == NULL) {
        fail("missing audit driver state");
    }
    char *index_end = NULL;
    long index_value = strtol(index_text, &index_end, 10);
    if (*index_text == '\0' || *index_end != '\0' || index_value < 0) {
        fail("invalid audit invocation index");
    }
    int index = (int)index_value;
    (void)requested_linker(argc, argv);
    const char *output = output_path(argc, argv);
    struct stat output_status;
    bool preexisting = lstat(output, &output_status) == 0;
    if (!preexisting && errno != ENOENT) {
        fail("cannot inspect output %s: %s", output, strerror(errno));
    }
    char nonce[64];
    snprintf(nonce, sizeof(nonce), "%ld-%d", (long)getpid(), index);
    long long started_ns = monotonic_ns();
    append_line(
        log_path,
        "{\"event\":\"link_start\",\"index\":%d,"
        "\"invoked_path\":\"%s\",\"nonce\":\"%s\",\"output\":\"%s\","
        "\"server_ns\":%lld,\"thread_mask\":%u}",
        index,
        argv[0],
        nonce,
        output,
        started_ns,
        thread_mask(argc, argv)
    );
    sleep_for_ms(delay_ms(linker, index));
    write_probe(output, log_path, nonce);
    append_line(
        log_path,
        "{\"event\":\"link_done\",\"index\":%d,"
        "\"nonce\":\"%s\",\"server_ns\":%lld,"
        "\"started_ns\":%lld}",
        index,
        nonce,
        monotonic_ns(),
        started_ns
    );
    return 0;
}
