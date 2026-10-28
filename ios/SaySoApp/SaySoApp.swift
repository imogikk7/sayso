import SwiftUI

@main
struct SaySoApp: App {
    var body: some Scene {
        WindowGroup {
            SpikeView()
        }
    }
}

/// Spike screen: setup steps for the Shortcut and an in-app test of the same /reply call.
struct SpikeView: View {
    @State private var response = ReplyStore.latest
    @State private var status = ""

    var body: some View {
        NavigationStack {
            List {
                Section("Set up the shortcut") {
                    Text("1. Shortcuts → + → Take Screenshot")
                    Text("2. Add “Reply from Screenshot” (SaySo), Screenshot = output of Take Screenshot")
                    Text("3. Settings → Accessibility → Touch → Back Tap → Double Tap → this shortcut")
                    Text("4. iPhone 15 Pro or newer: Settings → Action Button → Shortcut")
                }
                Section("Test the endpoint") {
                    Button("Send a test image") { Task { await sendTest() } }
                    if !status.isEmpty { Text(status).foregroundStyle(.secondary) }
                }
                if response != nil {
                    Section("Latest replies") {
                        RepliesSnippetView(response: response, copiedIndex: nil)
                    }
                }
            }
            .navigationTitle("SaySo")
        }
    }

    private func sendTest() async {
        status = "Sending…"
        let image = UIGraphicsImageRenderer(size: CGSize(width: 390, height: 844)).pngData { context in
            UIColor.systemBackground.setFill()
            context.fill(CGRect(x: 0, y: 0, width: 390, height: 844))
        }
        do {
            let started = Date()
            ReplyStore.latest = try await SaySoAPI.reply(screenshot: image)
            response = ReplyStore.latest
            status = String(format: "OK in %.1f s", Date().timeIntervalSince(started))
        } catch {
            status = "Error: \(error.localizedDescription)"
        }
    }
}
