#include <bits/stdc++.h>
#include <dirent.h>
#include <filesystem>
#include <csignal>
#include "hash_support.hpp"

using namespace std;
namespace fs = std::filesystem;
using Clock = chrono::steady_clock;
constexpr int HASH_LEN = 3;
// Bump this whenever hash selection, normalization, or rendered listings change.
constexpr const char* CACHE_VERSION = "biblioteca-hashes-v1";

struct Options {
    bool print_all = false, no_cache = false, rebuild = false, stats = false;
    unsigned jobs = 1;
    fs::path code = "../Codigo", cache = ".hash-cache";
};

string read_file(const fs::path& file) {
    ifstream in(file, ios::binary);
    if (!in) throw runtime_error("Não foi possível ler: " + file.string());
    string result((istreambuf_iterator<char>(in)), {});
    if (in.bad()) throw runtime_error("Erro de leitura: " + file.string());
    return result;
}

string typst_string(const string& text) {
    string result = "\"";
    for (char c : text) {
        if (c == '\\' || c == '"') result += '\\';
        if (c == '\n') result += "\\n";
        else if (c == '\r') result += "\\r";
        else if (c == '\t') result += "\\t";
        else result += c;
    }
    return result + "\"";
}

string lower(string text) {
    for (char& c : text) if (c >= 'A' && c <= 'Z') c ^= 32;
    return text;
}

// Keep the previous title/flag and brace-selection semantics, including vimrc.
struct Source {
    fs::path path;
    string content, title, rendered, diagnostics;
    vector<string> lines;
    set<string> flags;
    bool extra = false, cache_hit = false;
    size_t hashes = 0, cpp_calls = 0;

    Source(fs::path file, bool is_extra) : path(move(file)), content(read_file(path)), extra(is_extra) {
        istringstream input(content);
        string line;
        while (getline(input, line)) lines.push_back(line);
        line = lines.empty() ? "" : lines.front();
        size_t start = line.find('[');
        if (start != string::npos && !line.empty() && line.back() == ']') {
            istringstream items(line.substr(start + 1, line.size() - start - 2));
            string flag;
            while (getline(items, flag, ',')) if (!flag.empty()) flags.insert(flag);
            line.resize(start);
            while (!line.empty() && line.back() == ' ') line.pop_back();
        }
        title = line.size() > 2 ? line.substr(line[2] == ' ' ? 3 : 2) : line;
        if (extra) title = path.filename().string();
    }
};

// Preserve readdir order for sections/Extra; regular listings are sorted by title.
vector<pair<string, bool>> directory(const fs::path& path) {
    auto close_dir = [](DIR* dir) { closedir(dir); };
    unique_ptr<DIR, decltype(close_dir)> dir(opendir(path.c_str()), close_dir);
    if (!dir) throw runtime_error("Não foi possível abrir diretório: " + path.string());
    vector<pair<string, bool>> result;
    while (auto* entry = readdir(dir.get())) {
        if (entry->d_name[0] == '.') continue;
        fs::path child = path / entry->d_name;
        result.emplace_back(entry->d_name, fs::is_directory(child));
    }
    return result;
}

void collect(vector<Source>& sources, const fs::path& path, bool extra) {
    for (auto [name, is_dir] : directory(path)) {
        if (is_dir) collect(sources, path / name, extra);
        else sources.emplace_back(path / name, extra && name != "vimrc");
    }
}

struct Preprocessor {
    vector<string> command;
    string signature;
    bool cache_safe = true;

    Preprocessor() {
#ifdef __clang__
        string executable = "clang";
        command = {executable, "-E", "-x", "c++", "-dD", "-P", "-"};
        // Full Clang preprocessing can depend on includes and time macros.
        // Until those inputs are tracked, never reuse persistent results.
        cache_safe = false;
#else
        string executable = "cpp";
        command = {executable, "-dD", "-P", "-fpreprocessed"};
#endif
        if (const char* custom = getenv("HASH_CPP")) command[0] = executable = custom;
        if (executable.find('/') == string::npos) {
            istringstream paths(getenv("PATH") ? getenv("PATH") : "");
            string dir;
            bool found = false;
            while (getline(paths, dir, ':')) {
                fs::path candidate = (dir.empty() ? fs::path(".") : fs::path(dir)) / executable;
                if (access(candidate.c_str(), X_OK) == 0) {
                    executable = fs::canonical(candidate).string(); found = true; break;
                }
            }
            if (!found) throw runtime_error("Pré-processador não encontrado: " + command[0]);
        } else executable = fs::canonical(executable).string();
        command[0] = executable;
        auto version = hashing::run({executable, "--version"});
        if (version.status != 0) throw runtime_error("Falha ao identificar pré-processador: " + version.error);
        signature = string(CACHE_VERSION) + "\n" + to_string(HASH_LEN) + "\n" +
                    executable + "\n" + hashing::md5(read_file(executable)) + "\n" + version.output;
        for (const auto& arg : command) signature += "\narg:" + arg;
        // Environment variables that can influence preprocessing/byte handling.
        for (const char* key : {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "CPATH", "CPLUS_INCLUDE_PATH",
                                "C_INCLUDE_PATH", "GCC_EXEC_PREFIX", "COMPILER_PATH", "SOURCE_DATE_EPOCH"})
            signature += "\nenv:" + string(key) + "=" + (getenv(key) ? getenv(key) : "");
    }

    string hash(Source& source, int left, int right) const {
        string input;
        // The old first sed limits the selected snippet, not the source file.
        for (int i = left; i <= right && i - left < 10000; ++i)
            if (source.lines[i].compare(0, 2, "#w") != 0) input += source.lines[i] + '\n';
        ++source.hashes;
        ++source.cpp_calls;
        auto result = hashing::run(command, input);
        source.diagnostics += result.error;
        if (result.status != 0)
            throw runtime_error(source.path.string() + ":" + to_string(right + 1) +
                               ": pré-processador terminou com código " + to_string(result.status) + "\n" + result.error);
        string normalized;
        for (char c : result.output)
            if (c != ' ' && c != '\t' && c != '\n' && c != '\r' && c != '\v' && c != '\f') normalized += c;
        return hashing::md5(normalized).substr(0, HASH_LEN);
    }
};

bool is_comment(const string& line) {
    size_t first = line.find_first_not_of(" \t");
    return first == string::npos || line.compare(first, 2, "//") == 0 || line.compare(first, 2, "/*") == 0;
}

void render(Source& source, const Preprocessor& preprocessor) {
    bool started = false;
    vector<int> stack;
    for (int i = source.extra ? 0 : 2; i < int(source.lines.size()); ++i) {
        const string& line = source.lines[i];
        int start = i;
        for (char c : line) {
            if (c == '{') stack.push_back(i);
            if (c == '}') {
                if (stack.empty()) throw runtime_error("Chaves desbalanceadas: " + source.path.string());
                start = stack.back(); stack.pop_back();
            }
        }
        bool comment = is_comment(line);
        if (!comment) started = true;
        if (!source.extra && started) {
            string hash = preprocessor.hash(source, start, i);
            if (comment) { if (!stack.empty()) source.rendered.append(HASH_LEN + 1, ' '); }
            else source.rendered += hash + " ";
        }
        source.rendered += line + '\n';
    }
}

bool load_cache(Source& source, const fs::path& file, const string& key) {
    try {
        istringstream input(read_file(file));
        string version, stored_key, digest, count, payload;
        getline(input, version); getline(input, stored_key); getline(input, digest); getline(input, count);
        payload.assign(istreambuf_iterator<char>(input), {});
        if (version != CACHE_VERSION || stored_key != key || count.empty() ||
            count.find_first_not_of("0123456789") != string::npos ||
            digest != hashing::md5(count + "\n" + payload)) return false;
        source.hashes = stoull(count);
        source.rendered = move(payload);
        source.cache_hit = true;
        return true;
    } catch (const exception&) { return false; }
}

void store_cache(const Source& source, const fs::path& file, const string& key) {
    string count = to_string(source.hashes);
    string data = string(CACHE_VERSION) + "\n" + key + "\n" +
                  hashing::md5(count + "\n" + source.rendered) + "\n" + count + "\n" + source.rendered;
    string temporary = file.string() + ".tmp.XXXXXX";
    int fd = mkstemp(temporary.data());
    if (fd < 0) throw runtime_error("Não foi possível criar cache: " + file.string());
    size_t offset = 0;
    bool failed = false;
    while (offset < data.size()) {
        ssize_t n = write(fd, data.data() + offset, data.size() - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { failed = true; break; }
        offset += size_t(n);
    }
    if (close(fd) != 0) failed = true;
    if (!failed && rename(temporary.c_str(), file.c_str()) == 0) return;
    unlink(temporary.c_str());
    throw runtime_error("Falha ao gravar cache: " + file.string());
}

struct Section { string name; vector<Source> sources; };

int main(int argc, char** argv) {
    signal(SIGPIPE, SIG_IGN);
    try {
        Options options;
        if (const char* dir = getenv("CODE_DIR")) options.code = dir;
        for (int i = 1; i < argc; ++i) {
            string arg = argv[i];
            if (arg == "--printall") options.print_all = true;
            else if (arg == "--no-cache") options.no_cache = true;
            else if (arg == "--rebuild-cache") options.rebuild = true;
            else if (arg == "--stats") options.stats = true;
            else if (arg == "--cache-dir" && i + 1 < argc) options.cache = argv[++i];
            else if (arg == "--jobs" && i + 1 < argc) {
                string value = argv[++i];
                if (value.empty() || value.find_first_not_of("0123456789") != string::npos ||
                    stoul(value) < 1 || stoul(value) > 64) throw runtime_error("--jobs deve estar entre 1 e 64");
                options.jobs = stoul(value);
            } else throw runtime_error("Opção inválida ou incompleta: " + arg);
        }
        auto start = Clock::now();
        Preprocessor preprocessor;
        if (!preprocessor.cache_safe) options.no_cache = true;
        if (!options.no_cache) {
            error_code cache_error;
            fs::create_directories(options.cache, cache_error);
            if (cache_error) {
                cerr << "Aviso: cache indisponível (" << cache_error.message() << "); continuando sem cache\n";
                options.no_cache = true;
            }
        }
        vector<Section> sections;
        for (auto [name, is_dir] : directory(options.code)) {
            if (!is_dir || name == "Extra") continue;
            Section section{name, {}};
            collect(section.sources, options.code / name, false);
            sort(section.sources.begin(), section.sources.end(), [](const Source& a, const Source& b) {
                return lower(a.title) < lower(b.title);
            });
            sections.push_back(move(section));
        }
        Section extra{"Extra", {}};
        collect(extra.sources, options.code / "Extra", true);
        sections.push_back(move(extra));
        vector<Source*> work;
        size_t files_read = 0;
        for (auto& section : sections) for (auto& source : section.sources) {
            ++files_read;
            if (options.print_all || !source.flags.count("noprint")) work.push_back(&source);
        }
        atomic<size_t> next{0};
        atomic<bool> stop{false};
        mutex errors_mutex;
        exception_ptr error;
        auto worker = [&] {
            while (!stop) {
                size_t index = next++;
                if (index >= work.size()) break;
                Source& source = *work[index];
                try {
                    string key = hashing::md5(preprocessor.signature + "\nextra:" + to_string(source.extra) +
                                              "\ncontent:" + hashing::md5(source.content));
                    fs::path file = options.cache / (key + ".cache");
                    if (!options.no_cache && !options.rebuild && load_cache(source, file, key)) continue;
                    render(source, preprocessor);
                    if (!options.no_cache && source.diagnostics.empty()) {
                        try { store_cache(source, file, key); }
                        catch (const exception& e) { source.diagnostics += string("Aviso: ") + e.what() + '\n'; }
                    }
                } catch (...) {
                    lock_guard<mutex> lock(errors_mutex);
                    if (!error) error = current_exception();
                    stop = true;
                }
            }
        };
        vector<thread> workers;
        // Joining on thread creation failure also prevents std::terminate.
        try {
            for (unsigned i = 1; i < min<size_t>(options.jobs, work.size()); ++i) workers.emplace_back(worker);
        } catch (...) {
            stop = true;
            for (auto& thread : workers) thread.join();
            throw;
        }
        worker();
        for (auto& thread : workers) thread.join();
        if (error) rethrow_exception(error);
        cout << "#import \"template.typ\": biblioteca, listing\n#show: biblioteca\n\n";
        for (const auto& section : sections) {
            cout << "\n#heading(level: 1, " << typst_string(section.name) << ")\n\n";
            cerr << "=== " << section.name << " ===\n";
            for (const auto& source : section.sources) {
                if (!options.print_all && source.flags.count("noprint")) continue;
                cout << "#heading(level: 2, " << typst_string(source.title) << ")\n";
                cout << "#listing(" << typst_string(source.rendered)
                     << ", hashed: " << (source.extra ? "false" : "true") << ")\n\n";
                cerr << source.title << '\n' << source.diagnostics;
            }
            cerr << '\n';
        }
        if (options.stats) {
            size_t hashes = 0, calls = 0, hits = 0;
            for (auto* source : work) { hashes += source->hashes; calls += source->cpp_calls; hits += source->cache_hit; }
            cerr << "stats files_read=" << files_read << " files_printed=" << work.size()
                 << " hashes=" << hashes << " cpp_processes=" << calls << " identity_processes=1"
                 << " cache_hits=" << hits << " cache_misses=" << work.size() - hits
                 << " jobs=" << options.jobs << " seconds="
                 << chrono::duration<double>(Clock::now() - start).count() << '\n';
        }
        cout.flush();
        if (!cout) throw runtime_error("Erro ao escrever documento");
        return 0;
    } catch (const exception& error) {
        cerr << "Erro: " << error.what() << '\n';
        return 1;
    }
}
