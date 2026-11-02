import SwiftUI
import UIKit

/// Setup checklist: add the keyboard, allow Full Access, set up Back Tap, test the server; plus the last replies.
struct SetupView: View {
    @Environment(\.scenePhase) private var scenePhase
    @State private var keyboardOpened = SharedStore.keyboardOpenedWithFullAccess
    @State private var shortcutDone = SharedStore.shortcutDone
    @State private var serverStatus: String?
    @State private var serverOK = false
    @State private var testing = false
    @State private var tryText = ""
    @State private var response = ReplyStore.latest

    private let totalSteps = 4

    private var keyboardReady: Bool { keyboardOpened != nil }

    private var doneSteps: Int {
        (keyboardReady ? 2 : 0) + (shortcutDone ? 1 : 0) + (serverOK ? 1 : 0)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.backdrop
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        header
                        SectionTitle(text: "Keyboard").padding(.top, 4)
                        keyboardStep
                        fullAccessStep
                        SectionTitle(text: "Reply from a screenshot").padding(.top, 6)
                        shortcutStep
                        SectionTitle(text: "Server").padding(.top, 6)
                        serverStep
                        if let response {
                            LastRepliesCard(response: response).padding(.top, 6)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 12)
                    .padding(.bottom, 32)
                }
            }
            .toolbar(.hidden, for: .navigationBar)
            .onAppear(perform: refresh)
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { refresh() }
            }
            // The keyboard records that it opened with Full Access; typing in the field below is that first open.
            .onChange(of: tryText) { _, _ in
                keyboardOpened = SharedStore.keyboardOpenedWithFullAccess
            }
            .onChange(of: shortcutDone) { _, value in SharedStore.shortcutDone = value }
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack(alignment: .center, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Set up").font(Theme.title(34))
                Text(doneSteps == totalSteps
                     ? "All set. SaySo works in every chat."
                     : "A few taps and SaySo writes like you in every chat.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            ProgressRing(done: doneSteps, total: totalSteps)
        }
    }

    // MARK: - Steps

    private var keyboardStep: some View {
        StepCard(number: 1, title: "Add the SaySo keyboard", done: keyboardReady,
                 detail: "Add it to your iPhone's keyboards, next to your usual ones.") {
            PathLine(steps: ["Settings", "General", "Keyboard", "Keyboards", "Add New Keyboard", "SaySo"])
            Button(action: openSettings) {
                Label("Open Settings", systemImage: "gear")
            }
            .buttonStyle(PrimaryButtonStyle())
        }
    }

    private var fullAccessStep: some View {
        StepCard(number: 2, title: "Allow Full Access", done: keyboardReady,
                 detail: "Tap SaySo in that list and turn on Allow Full Access, so it can reach your style. Then open the keyboard once, below.") {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "globe")
                    .font(.body.weight(.semibold))
                    .foregroundStyle(Color.accentColor)
                    .padding(.top, 1)
                TextField("Type here, then switch to SaySo 🌐", text: $tryText, axis: .vertical)
                    .lineLimit(1...4)
            }
            .padding(12)
            .background(Color.primary.opacity(0.05), in: .rect(cornerRadius: Theme.card))
            .overlay(RoundedRectangle(cornerRadius: Theme.card).stroke(Color.accentColor.opacity(0.2)))
            if keyboardReady {
                Label("SaySo keyboard opened with Full Access", systemImage: "checkmark.seal.fill")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Color.green)
            }
        }
    }

    private var shortcutStep: some View {
        StepCard(number: 3, title: "Set up the Back Tap shortcut", done: shortcutDone,
                 detail: "Double-tap the back of your iPhone on any chat and SaySo writes three replies from a screenshot.") {
            ShortcutFlow()
            NoteBox(icon: "square.on.square.dashed", text: """
            In Shortcuts: + → Take Screenshot → Reply from Screenshot (SaySo, leave Audience empty). \
            It shows the replies and copies the first one; adding Choose from List → Copy to Clipboard is optional.
            """)
            PathLine(steps: ["Settings", "Accessibility", "Touch", "Back Tap", "Double Tap", "this shortcut"])
            HStack(spacing: 12) {
                Button(action: openShortcuts) {
                    Label("Open Shortcuts", systemImage: "square.2.layers.3d")
                }
                .buttonStyle(SoftButtonStyle())
                Spacer(minLength: 8)
                Toggle(isOn: $shortcutDone) {
                    Text("I've set it up").font(.subheadline.weight(.semibold))
                }
                .tint(Color.accentColor)
                .fixedSize()
            }
        }
    }

    private var serverStep: some View {
        StepCard(number: 4, title: "Check the connection", done: serverOK,
                 detail: serverStatus ?? "Makes sure SaySo can reach your styles.") {
            Button {
                Task { await test() }
            } label: {
                HStack(spacing: 8) {
                    if testing {
                        ProgressView().tint(.white)
                    } else {
                        Image(systemName: serverOK ? "checkmark.icloud" : "bolt.horizontal.icloud")
                    }
                    Text(testing ? "Testing…" : "Test now")
                }
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(testing)
        }
    }

    // MARK: - Actions

    private func refresh() {
        keyboardOpened = SharedStore.keyboardOpenedWithFullAccess
        response = ReplyStore.latest
    }

    private func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
    }

    private func openShortcuts() {
        if let url = URL(string: "shortcuts://") { UIApplication.shared.open(url) }
    }

    private func test() async {
        testing = true
        serverStatus = "Testing…"
        let started = Date()
        do {
            let styles = try await SaySoAPI.styles()
            serverOK = true
            serverStatus = String(format: "Connected in %.1f s · %d style%@", Date().timeIntervalSince(started),
                                  styles.count, styles.count == 1 ? "" : "s")
        } catch {
            serverOK = false
            serverStatus = error.localizedDescription
        }
        testing = false
    }
}
