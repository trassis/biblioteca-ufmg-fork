#pragma once

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <spawn.h>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

extern char** environ;

namespace hashing {
// MD5 as specified in RFC 1321. Used for compatibility, not for security.
inline std::string md5(std::string_view input) {
    static const uint32_t k[] = {
        0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,0xf57c0faf,0x4787c62a,0xa8304613,0xfd469501,
        0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,0x6b901122,0xfd987193,0xa679438e,0x49b40821,
        0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,0xd62f105d,0x02441453,0xd8a1e681,0xe7d3fbc8,
        0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a,
        0xfffa3942,0x8771f681,0x6d9d6122,0xfde5380c,0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70,
        0x289b7ec6,0xeaa127fa,0xd4ef3085,0x04881d05,0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665,
        0xf4292244,0x432aff97,0xab9423a7,0xfc93a039,0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1,
        0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,0xf7537e82,0xbd3af235,0x2ad7d2bb,0xeb86d391
    };
    static const unsigned shifts[] = {
        7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,
        5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,
        4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,
        6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21
    };
    std::string data(input);
    uint64_t bits = uint64_t(data.size()) * 8;
    data += char(0x80);
    while (data.size() % 64 != 56) data += '\0';
    for (unsigned i = 0; i < 8; ++i) data += char(bits >> (8 * i));
    uint32_t state[] = {0x67452301,0xefcdab89,0x98badcfe,0x10325476};
    for (size_t offset = 0; offset < data.size(); offset += 64) {
        uint32_t words[16] = {};
        for (unsigned i = 0; i < 64; ++i)
            words[i / 4] |= uint32_t(static_cast<unsigned char>(data[offset + i])) << (8 * (i % 4));
        uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
        for (unsigned i = 0; i < 64; ++i) {
            uint32_t f, g;
            if (i < 16) { f = (b & c) | (~b & d); g = i; }
            else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; }
            else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16; }
            else { f = c ^ (b | ~d); g = (7 * i) % 16; }
            uint32_t x = a + f + k[i] + words[g];
            a = d; d = c; c = b;
            b += (x << shifts[i]) | (x >> (32 - shifts[i]));
        }
        state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    }
    std::string result;
    for (auto word : state) for (unsigned i = 0; i < 4; ++i) {
        unsigned byte = (word >> (8 * i)) & 255;
        result += "0123456789abcdef"[byte >> 4];
        result += "0123456789abcdef"[byte & 15];
    }
    return result;
}

struct ProcessResult { std::string output, error; int status; };

// Drain stdout AND stderr while feeding stdin: large snippets cannot fill a
// pipe and deadlock. No shell, shared temporary files, or inherited pipe FDs.
inline ProcessResult run(const std::vector<std::string>& args, std::string_view input = {}) {
    struct Pipes {
        int fd[6] = {-1,-1,-1,-1,-1,-1};
        ~Pipes() { for (int f : fd) if (f >= 0) close(f); }
        void shut(int index) { if (fd[index] >= 0) close(fd[index]); fd[index] = -1; }
    } pipes;
    for (int i = 0; i < 6; i += 2)
        if (pipe2(pipes.fd + i, O_CLOEXEC) < 0)
            throw std::runtime_error("pipe: " + std::string(strerror(errno)));
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_adddup2(&actions, pipes.fd[0], STDIN_FILENO);
    posix_spawn_file_actions_adddup2(&actions, pipes.fd[3], STDOUT_FILENO);
    posix_spawn_file_actions_adddup2(&actions, pipes.fd[5], STDERR_FILENO);
    for (int f : pipes.fd) posix_spawn_file_actions_addclose(&actions, f);
    std::vector<char*> argv;
    for (const auto& arg : args) argv.push_back(const_cast<char*>(arg.c_str()));
    argv.push_back(nullptr);
    pid_t pid;
    int error = posix_spawnp(&pid, argv[0], &actions, nullptr, argv.data(), environ);
    posix_spawn_file_actions_destroy(&actions);
    if (error) throw std::runtime_error(args[0] + ": " + strerror(error));
    pipes.shut(0); pipes.shut(3); pipes.shut(5);
    ProcessResult result;
    size_t sent = 0;
    bool io_error = false;
    for (int i : {1, 2, 4}) {
        int flags = fcntl(pipes.fd[i], F_GETFL);
        if (flags < 0 || fcntl(pipes.fd[i], F_SETFL, flags | O_NONBLOCK) < 0) {
            io_error = true;
            pipes.shut(i);
        }
    }
    while (pipes.fd[1] >= 0 || pipes.fd[2] >= 0 || pipes.fd[4] >= 0) {
        if (sent == input.size()) pipes.shut(1);
        if (pipes.fd[1] < 0 && pipes.fd[2] < 0 && pipes.fd[4] < 0) break;
        pollfd events[] = {{pipes.fd[1], POLLOUT, 0}, {pipes.fd[2], POLLIN, 0}, {pipes.fd[4], POLLIN, 0}};
        int ready = poll(events, 3, -1);
        if (ready < 0) {
            if (errno == EINTR) continue;
            io_error = true;
            for (int i : {1, 2, 4}) pipes.shut(i);
            break;
        }
        if (events[0].revents) {
            ssize_t n = write(pipes.fd[1], input.data() + sent, input.size() - sent);
            if (n > 0) sent += size_t(n);
            else if (n < 0 && errno != EAGAIN && errno != EINTR) {
                io_error = true;
                pipes.shut(1);
            }
        }
        for (int j : {1, 2}) if (events[j].revents) {
            int index = j == 1 ? 2 : 4;
            char buffer[16384];
            ssize_t n = read(pipes.fd[index], buffer, sizeof buffer);
            if (n > 0) (j == 1 ? result.output : result.error).append(buffer, size_t(n));
            else if (n == 0) pipes.shut(index);
            else if (errno != EAGAIN && errno != EINTR) { io_error = true; pipes.shut(index); }
        }
    }
    int status;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno != EINTR) throw std::runtime_error("waitpid failed");
    }
    result.status = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    if (io_error || sent != input.size())
        throw std::runtime_error(args[0] + ": erro na comunicação com o processo\n" + result.error);
    return result;
}
} // namespace hashing
