#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define CONTROL_SOCKET "/run/linkbench-control/observer.sock"
#define CONTROL_BIN "/opt/control/bin/../bin"
#define BUFFER_SIZE 16384
#ifndef PR_SET_PTRACER
#define PR_SET_PTRACER 0x59616d61
#endif
#ifndef PR_SET_PTRACER_ANY
#define PR_SET_PTRACER_ANY ((unsigned long)-1)
#endif

static const unsigned char CONTROL_AUTH_KEY[] =
    "phase4-observer-auth-3f99d7c1";
static const char *SELF_NAME = "unknown";

static const char *program_name(const char *path) {
    const char *slash = strrchr(path, '/');
    return slash == NULL ? path : slash + 1;
}

static void die(const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    fprintf(stderr, "controlled tool: ");
    vfprintf(stderr, format, arguments);
    fprintf(stderr, "\n");
    va_end(arguments);
    exit(70);
}

static void write_all(int descriptor, const char *data, size_t length) {
    while (length > 0) {
        ssize_t written = write(descriptor, data, length);
        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            die("write failed: %s", strerror(errno));
        }
        data += written;
        length -= (size_t)written;
    }
}

static size_t read_response(
    int descriptor,
    char *response,
    size_t capacity,
    bool stop_at_newline
) {
    size_t used = 0;
    while (used + 1 < capacity) {
        ssize_t count = read(descriptor, response + used, capacity - used - 1);
        if (count < 0) {
            if (errno == EINTR) {
                continue;
            }
            die("observer read failed: %s", strerror(errno));
        }
        if (count == 0) {
            break;
        }
        used += (size_t)count;
        if (stop_at_newline && memchr(response, '\n', used) != NULL) {
            break;
        }
    }
    response[used] = '\0';
    return used;
}

static void hmac_hex(
    const unsigned char *data,
    size_t length,
    char output[EVP_MAX_MD_SIZE * 2 + 1]
) {
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_length = 0;
    if (
        HMAC(
            EVP_sha256(),
            CONTROL_AUTH_KEY,
            (int)(sizeof(CONTROL_AUTH_KEY) - 1),
            data,
            length,
            digest,
            &digest_length
        ) == NULL
    ) {
        die("HMAC failed");
    }
    for (unsigned int index = 0; index < digest_length; ++index) {
        sprintf(output + index * 2, "%02x", digest[index]);
    }
    output[digest_length * 2] = '\0';
}

static void exchange(const char *request, char *response, size_t capacity) {
    int descriptor = socket(AF_UNIX, SOCK_STREAM, 0);
    if (descriptor < 0) {
        die("socket failed: %s", strerror(errno));
    }
    struct sockaddr_un address;
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
    if (strlen(CONTROL_SOCKET) >= sizeof(address.sun_path)) {
        die("control socket path is too long");
    }
    strcpy(address.sun_path, CONTROL_SOCKET);
    if (connect(descriptor, (struct sockaddr *)&address, sizeof(address)) < 0) {
        die("cannot connect to observer: %s", strerror(errno));
    }
    char challenge_line[256];
    if (
        read_response(
            descriptor,
            challenge_line,
            sizeof(challenge_line),
            true
        ) == 0
    ) {
        die("observer returned no challenge");
    }
    char challenge[129];
    if (sscanf(challenge_line, "CHALLENGE\t%128s", challenge) != 1) {
        die("observer challenge is invalid: %s", challenge_line);
    }
    char material[BUFFER_SIZE];
    int material_length = snprintf(
        material,
        sizeof(material),
        "%s\n%s",
        challenge,
        request
    );
    if (material_length < 0 || (size_t)material_length >= sizeof(material)) {
        die("authentication material is too large");
    }
    char authentication[EVP_MAX_MD_SIZE * 2 + 1];
    hmac_hex(
        (const unsigned char *)material,
        (size_t)material_length,
        authentication
    );
    char envelope[BUFFER_SIZE];
    int envelope_length = snprintf(
        envelope,
        sizeof(envelope),
        "AUTH\t%s\t%s\t%s",
        SELF_NAME,
        authentication,
        request
    );
    if (envelope_length < 0 || (size_t)envelope_length >= sizeof(envelope)) {
        die("authenticated request is too large");
    }
    write_all(descriptor, envelope, (size_t)envelope_length);
    if (shutdown(descriptor, SHUT_WR) < 0) {
        die("socket shutdown failed: %s", strerror(errno));
    }
    size_t used = read_response(descriptor, response, capacity, false);
    close(descriptor);
    if (used == 0) {
        die("observer returned no response");
    }
    if (strncmp(response, "ERROR\t", 6) == 0) {
        die("observer rejected request: %s", response + 6);
    }
}

static const char *requested_linker(int argc, char **argv) {
    const char *prefix = "-fuse-ld=";
    size_t prefix_length = strlen(prefix);
    for (int index = 1; index < argc; ++index) {
        if (strncmp(argv[index], prefix, prefix_length) == 0) {
            return argv[index] + prefix_length;
        }
    }
    return NULL;
}

static const char *output_path(int argc, char **argv) {
    for (int index = 1; index + 1 < argc; ++index) {
        if (strcmp(argv[index], "-o") == 0) {
            return argv[index + 1];
        }
    }
    return NULL;
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

static bool unexpected_thread_control(int argc, char **argv) {
    for (int index = 1; index < argc; ++index) {
        const char *argument = argv[index];
        if (
            strcmp(argument, "-Wl,--threads") == 0
            || strcmp(argument, "-Wl,--thread-count=2") == 0
            || strcmp(argument, "-Wl,--threads=2") == 0
            || strcmp(argument, "-Wl,--no-fork") == 0
        ) {
            continue;
        }
        if (
            argument[0] == '-'
            && (
                strstr(argument, "thread") != NULL
                || strstr(argument, "fork") != NULL
                || strstr(argument, "--jobs") != NULL
                || strncmp(argument, "-Wl,-j", 6) == 0
                || strcmp(argument, "-j") == 0
            )
        ) {
            return true;
        }
    }
    return false;
}

static void sleep_milliseconds(int milliseconds) {
    struct timespec requested = {
        .tv_sec = milliseconds / 1000,
        .tv_nsec = (long)(milliseconds % 1000) * 1000000L,
    };
    while (nanosleep(&requested, &requested) < 0) {
        if (errno != EINTR) {
            die("nanosleep failed: %s", strerror(errno));
        }
    }
}

/* Run one of the argument-free processes the driver brackets each link with.
   These are executed the same way as the linker and report the same version
   banner, so the only thing that separates them from the link's linker is that
   they never receive the link's arguments. */
static void run_bracketing_process(const char *name) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "%s/%s", CONTROL_BIN, name);
    pid_t child = fork();
    if (child < 0) {
        die("cannot fork %s: %s", name, strerror(errno));
    }
    if (child == 0) {
        execl(path, path, (char *)NULL);
        die("cannot execute %s: %s", path, strerror(errno));
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) {
            die("%s waitpid failed: %s", name, strerror(errno));
        }
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        die("%s did not exit cleanly", name);
    }
}

static int run_driver(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts("controlled gcc 1.0");
        return 0;
    }
    const char *requested = requested_linker(argc, argv);
    if (requested == NULL) {
        requested = "bfd";
    }
    char request[BUFFER_SIZE];
    char response[BUFFER_SIZE];
    snprintf(request, sizeof(request), "ROUTE\t%s\n", requested);
    exchange(request, response, sizeof(response));
    char actual[32];
    char decoy[32];
    int leading = 0;
    int trailing = 0;
    if (
        sscanf(
            response,
            "ROUTE\t%31s\t%31s\t%d\t%d",
            actual,
            decoy,
            &leading,
            &trailing
        ) != 4
    ) {
        die("invalid route response: %s", response);
    }
    char decoy_name[64];
    snprintf(decoy_name, sizeof(decoy_name), "ld.%s", decoy);
    for (int repeat = 0; repeat < leading; ++repeat) {
        run_bracketing_process(decoy_name);
    }
    char linker_path[PATH_MAX];
    snprintf(linker_path, sizeof(linker_path), "%s/ld.%s", CONTROL_BIN, actual);
    char **linker_argv = calloc((size_t)argc + 1, sizeof(char *));
    if (linker_argv == NULL) {
        die("calloc failed");
    }
    linker_argv[0] = linker_path;
    for (int index = 1; index < argc; ++index) {
        linker_argv[index] = argv[index];
    }
    linker_argv[argc] = NULL;
    pid_t child = fork();
    if (child < 0) {
        die("cannot fork linker: %s", strerror(errno));
    }
    if (child == 0) {
        execv(linker_path, linker_argv);
        die("cannot execute %s: %s", linker_path, strerror(errno));
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) {
            die("waitpid failed: %s", strerror(errno));
        }
    }
    if (WIFEXITED(status)) {
        int linker_returncode = WEXITSTATUS(status);
        if (linker_returncode != 0) {
            return linker_returncode;
        }
        for (int repeat = 0; repeat < trailing; ++repeat) {
            run_bracketing_process(decoy_name);
        }
        run_bracketing_process("ld.gold-helper");
        return 0;
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 70;
}

static void write_probe_launcher(const char *path, const char *nonce) {
    int descriptor = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0755);
    if (descriptor < 0) {
        die("cannot create output %s: %s", path, strerror(errno));
    }
    if (fchmod(descriptor, 0755) < 0) {
        die("cannot chmod output %s: %s", path, strerror(errno));
    }
    char script[BUFFER_SIZE];
    int length = snprintf(
        script,
        sizeof(script),
        "#!/bin/sh\nexec %s/probe --nonce %s \"$@\"\n",
        CONTROL_BIN,
        nonce
    );
    if (length < 0 || (size_t)length >= sizeof(script)) {
        die("probe launcher is too large");
    }
    write_all(descriptor, script, (size_t)length);
    close(descriptor);
}

static void write_corrupt_output(const char *path) {
    int descriptor = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0755);
    if (descriptor < 0) {
        die("cannot create corrupt output: %s", strerror(errno));
    }
    const char content[] = "this is not an executable format\n";
    write_all(descriptor, content, sizeof(content) - 1);
    fchmod(descriptor, 0755);
    close(descriptor);
}

static void write_non_regular_output(const char *path, const char *nonce) {
    char target[PATH_MAX];
    int length = snprintf(
        target,
        sizeof(target),
        "%s.control-target-%s",
        path,
        nonce
    );
    if (length < 0 || (size_t)length >= sizeof(target)) {
        die("non-regular output target is too long");
    }
    write_probe_launcher(target, nonce);
    if (symlink(target, path) < 0) {
        die("cannot create non-regular output: %s", strerror(errno));
    }
}

static const char *linker_id_from_name(const char *name) {
    if (strncmp(name, "ld.", 3) == 0 && name[3] != '\0') {
        return name + 3;
    }
    return NULL;
}

static int run_linker(const char *linker, int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        char request[BUFFER_SIZE];
        char response[BUFFER_SIZE];
        snprintf(request, sizeof(request), "VERSION\t%s\n", linker);
        exchange(request, response, sizeof(response));
        if (strncmp(response, "VERSION\t", 8) != 0) {
            die("invalid version response: %s", response);
        }
        fputs(response + 8, stdout);
        return 0;
    }
    size_t name_length = strlen(linker);
    if (name_length > 4 && strcmp(linker + name_length - 4, "-alt") == 0) {
        return 0;
    }
    const char *requested = requested_linker(argc, argv);
    const char *output = output_path(argc, argv);
    if (requested == NULL || output == NULL) {
        die("link invocation is missing selector or output");
    }
    struct stat output_status;
    int output_preexisting = 0;
    if (lstat(output, &output_status) == 0) {
        output_preexisting = 1;
    } else if (errno != ENOENT) {
        die("cannot inspect output %s: %s", output, strerror(errno));
    }
    char request[BUFFER_SIZE];
    char response[BUFFER_SIZE];
    snprintf(
        request,
        sizeof(request),
        "LINK\t%s\t%s\t%s\t%u\t%d\t%d\n",
        linker,
        requested,
        output,
        thread_mask(argc, argv),
        output_preexisting,
        unexpected_thread_control(argc, argv) ? 1 : 0
    );
    exchange(request, response, sizeof(response));
    int invocation_index = -1;
    int delay_ms = -1;
    char nonce[65];
    char action[32];
    if (
        sscanf(
            response,
            "LINK\t%d\t%d\t%64s\t%31s",
            &invocation_index,
            &delay_ms,
            nonce,
            action
        ) != 4
    ) {
        die("invalid link response: %s", response);
    }
    sleep_milliseconds(delay_ms);

    int returncode = 0;
    if (strcmp(action, "success") == 0 || strcmp(action, "probe_fail") == 0) {
        write_probe_launcher(output, nonce);
    } else if (strcmp(action, "non_regular") == 0) {
        write_non_regular_output(output, nonce);
    } else if (strcmp(action, "corrupt") == 0) {
        write_corrupt_output(output);
    } else if (strcmp(action, "no_output") == 0) {
        returncode = 0;
    } else if (strcmp(action, "fail") == 0) {
        returncode = 1;
    } else {
        die("unknown observer action: %s", action);
    }

    snprintf(
        request,
        sizeof(request),
        "DONE\t%d\t%s\t%s\t%s\n",
        invocation_index,
        nonce,
        output,
        action
    );
    exchange(request, response, sizeof(response));
    if (strncmp(response, "DONE\tOK", 7) != 0) {
        die("invalid completion response: %s", response);
    }
    return returncode;
}

static int run_probe(int argc, char **argv) {
    if (argc < 5 || strcmp(argv[1], "--nonce") != 0) {
        die("probe launcher arguments are invalid");
    }
    char request[BUFFER_SIZE];
    char response[BUFFER_SIZE];
    snprintf(
        request,
        sizeof(request),
        "PROBE\t%s\t%s\t%s\n",
        argv[2],
        argv[3],
        argv[4]
    );
    exchange(request, response, sizeof(response));
    int returncode = -1;
    char stdout_token[256];
    char stderr_token[256];
    if (
        sscanf(
            response,
            "PROBE\t%d\t%255s\t%255s",
            &returncode,
            stdout_token,
            stderr_token
        ) != 3
    ) {
        die("invalid probe response: %s", response);
    }
    if (strcmp(stdout_token, "-") != 0) {
        printf("%s\n", stdout_token);
    }
    if (strcmp(stderr_token, "-") != 0) {
        fprintf(stderr, "%s\n", stderr_token);
    }
    return returncode;
}

int main(int argc, char **argv) {
    const char *name = program_name(argv[0]);
    SELF_NAME = name;
    if (prctl(PR_SET_NAME, SELF_NAME, 0, 0, 0) < 0) {
        die("cannot set controlled process name: %s", strerror(errno));
    }
    if (prctl(PR_SET_DUMPABLE, 1, 0, 0, 0) < 0) {
        die("cannot make controlled process inspectable: %s", strerror(errno));
    }
    if (prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0) < 0) {
        die("cannot authorize controlled process inspection: %s", strerror(errno));
    }
    if (strcmp(name, "gcc") == 0) {
        return run_driver(argc, argv);
    }
    if (strcmp(name, "probe") == 0) {
        return run_probe(argc, argv);
    }
    if (strcmp(name, "ld.gold-helper") == 0) {
        if (argc == 2 && strcmp(argv[1], "--version") == 0) {
            puts("post-link helper 1.0");
        }
        return 0;
    }
    const char *linker = linker_id_from_name(name);
    if (linker != NULL) {
        return run_linker(linker, argc, argv);
    }
    die("unsupported executable name: %s", name);
    return 70;
}
