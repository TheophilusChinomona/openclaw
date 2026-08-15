import Foundation

public struct HookJob: Sendable {
    public let text: String
    public let timestamp: Date

    public init(text: String, timestamp: Date) {
        self.text = text
        self.timestamp = timestamp
    }
}

public actor HookExecutor {
    private let config: SwabbleConfig
    private var lastRun: Date?
    private let hostname: String

    public init(config: SwabbleConfig) {
        self.config = config
        hostname = Host.current().localizedName ?? "host"
    }

    public func shouldRun() -> Bool {
        guard config.hook.cooldownSeconds > 0 else { return true }
        if let lastRun, Date().timeIntervalSince(lastRun) < config.hook.cooldownSeconds {
            return false
        }
        return true
    }

    public func run(job: HookJob) async throws {
        guard shouldRun() else { return }
        guard !config.hook.command.isEmpty else { throw NSError(
            domain: "Hook",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "hook command not set"]) }

        let prefix = config.hook.prefix.replacingOccurrences(of: "${hostname}", with: hostname)
        let payload = prefix + job.text

        let process = Process()
        
        // Sanitize arguments to prevent command injection.
        // If the command is a shell, arguments should be passed as a single string to -c.
        // Otherwise, arguments should be treated as literal arguments.
        let commandPath = config.hook.command
        let arguments = config.hook.args + [payload]

        // Basic check for common shells. This is not exhaustive but covers common cases.
        let shellExecutables = ["/bin/sh", "/bin/bash", "/bin/zsh", "/bin/csh", "cmd.exe", "powershell.exe"]
        let isShellCommand = shellExecutables.contains(where: { commandPath.lowercased().hasSuffix($0) })

        if isShellCommand {
            // If it's a shell, combine arguments into a single string for -c
            // and ensure proper escaping if necessary for the specific shell.
            // For simplicity, we'll join them directly, assuming the user intends
            // the arguments to be interpreted by the shell. A more robust solution
            // would involve specific shell escaping.
            let fullCommand = arguments.joined(separator: " ")
            process.executableURL = URL(fileURLWithPath: commandPath)
            process.arguments = ["-c", fullCommand]
        } else {
            // For non-shell commands, pass arguments directly.
            process.executableURL = URL(fileURLWithPath: commandPath)
            process.arguments = arguments
        }

        var env = ProcessInfo.processInfo.environment
        env["SWABBLE_TEXT"] = job.text
        env["SWABBLE_PREFIX"] = prefix
        for (k, v) in config.hook.env {
            env[k] = v
        }
        process.environment = env

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        try process.run()

        let timeoutNanos = UInt64(max(config.hook.timeoutSeconds, 0.1) * 1_000_000_000)
        try await withThrowingTaskGroup(of: Void.self) { group in
            group.addTask {
                process.waitUntilExit()
            }
            group.addTask {
                try await Task.sleep(nanoseconds: timeoutNanos)
                if process.isRunning {
                    process.terminate()
                }
            }
            try await group.next()
            group.cancelAll()
        }
        lastRun = Date()
    }
}