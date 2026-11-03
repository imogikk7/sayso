import SwiftUI
import UIKit

/// The Settings tab: the app's language first, then the setup checklist (add the keyboard, allow Full Access, set up
/// the Back Tap shortcut, test the server) and the last screenshot's replies.
struct SetupView: View {
    /// The iCloud link to the ready-made Back Tap shortcut (Shortcuts → the shortcut → Share → Copy iCloud Link).
    /// Opening it shows the shortcut in Shortcuts with an Add Shortcut button. The only place this link lives.
    static let shortcutURL = URL(string: "https://www.icloud.com/shortcuts/1420189edef04aa9bb90530d63176a1b")!

    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.openURL) private var openURL
    @State private var keyboardOpened = SharedStore.keyboardOpenedWithFullAccess
    @State private var shortcutDone = SharedStore.shortcutDone
    @State private var serverStatus: String?
    @State private var serverOK = false
    @State private var testing = false
    @State private var tryText = ""
    @State private var response = ReplyStore.latest
    @AppStorage(AppLanguage.storageKey, store: SharedStore.defaults) private var language = AppLanguage.system.rawValue

    private let totalSteps = 4

    private var keyboardReady: Bool { keyboardOpened != nil }

    private var doneSteps: Int {
        (keyboardReady ? 2 : 0) + (shortcutDone ? 1 : 0) + (serverOK ? 1 : 0)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.backdrop
                ScrollView(.vertical) {
                    VStack(alignment: .leading, spacing: 16) {
                        header
                        languageCard
                        setupHeader.padding(.top, 10)
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
                    .pageWidth()
                }
                .scrollBounceBehavior(.basedOnSize, axes: .horizontal)
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
        VStack(alignment: .leading, spacing: 4) {
            Text("Settings").font(Theme.title(34))
            Text("Language, and a few taps so SaySo writes like you in every chat.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: - Language

    private var languageCard: some View {
        SettingsCard(icon: "globe", colors: TileColors.sky, title: "Language",
                     subtitle: "For SaySo's screens, keyboard and shortcut. What it writes for you stays in your own language.") {
            VStack(spacing: 10) {
                ForEach(AppLanguage.allCases) { option in
                    SelectTile(icon: Self.icon(for: option), title: option.title, selected: language == option.rawValue) {
                        AppLanguage.save(option)
                    }
                }
                NoteBox(icon: "arrow.clockwise", text: "Shortcuts and Siri switch after you close SaySo and open it again.")
            }
        }
    }

    private static func icon(for language: AppLanguage) -> String {
        switch language {
        case .system: "iphone"
        case .en: "character.book.closed"
        case .ru: "character.book.closed.fill"
        }
    }

    // MARK: - Set up

    private var setupHeader: some View {
        HStack(alignment: .center, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Set up").font(Theme.title(26))
                Text(doneSteps == totalSteps
                     ? "All set. SaySo works in every chat."
                     : "A few taps and SaySo writes like you in every chat.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            ProgressRing(done: doneSteps, total: totalSteps, size: 84)
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
                 detail: "Double-tap the back of your iPhone on any chat: SaySo writes three replies from a screenshot, you tap one and it's copied.") {
            ShortcutFlow()
            // The main path: one tap imports the ready shortcut, then Back Tap is assigned in Settings.
            Button {
                openURL(Self.shortcutURL)
            } label: {
                Label("Add the SaySo shortcut", systemImage: "plus.square.on.square")
                    .multilineTextAlignment(.center)
            }
            .buttonStyle(PrimaryButtonStyle())
            NumberedSteps(steps: [
                "Tap the button above, then Add Shortcut.",
                "Turn on Back Tap: Double Tap, then choose the shortcut.",
            ])
            PathLine(steps: ["Settings", "Accessibility", "Touch", "Back Tap", "Double Tap", "this shortcut"])
            // For people who'd rather build it: the same shortcut by hand, closed until asked for.
            DisclosureGroup {
                NumberedSteps(steps: [
                    "Open Shortcuts and tap + to make a new shortcut.",
                    "Add the action Take Screenshot.",
                    "Add Reply with SaySo (search for SaySo). Leave Audience empty, so it asks every time.",
                    "Add Choose from List. It picks up the replies by itself.",
                    "Add Copy to Clipboard. It copies the reply you choose.",
                    "Name it, for example SaySo reply, and tap Done.",
                    "Assign it to Back Tap the same way, as in step 2 above.",
                ])
                .padding(.top, 8)
            } label: {
                Label("Build it yourself", systemImage: "hammer")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Color.accentColor)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .tint(Color.accentColor)
            NoteBox(icon: "keyboard", text: "The replies also wait in the SaySo keyboard: switch to it in the chat and tap one to put it in, no copying needed.")
            // The switch's label is a separate Text so it can wrap: a Toggle with .fixedSize() never got narrower than
            // its one-line label plus the switch, however little room the button left it.
            HStack(spacing: 12) {
                Button(action: openShortcuts) {
                    Label("Open Shortcuts", systemImage: "square.2.layers.3d")
                }
                .buttonStyle(SoftButtonStyle())
                Spacer(minLength: 8)
                Text("I've set it up")
                    .font(.subheadline.weight(.semibold))
                    .multilineTextAlignment(.trailing)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityHidden(true)
                Toggle("I've set it up", isOn: $shortcutDone)
                    .labelsHidden()
                    .tint(Color.accentColor)
            }
        }
    }

    private var serverStep: some View {
        StepCard(number: 4, title: "Check the connection", done: serverOK,
                 detail: serverStatus ?? L("Makes sure SaySo can reach your styles.")) {
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
        serverStatus = L("Testing…")
        let started = Date()
        do {
            let styles = try await SaySoAPI.styles()
            serverOK = true
            serverStatus = Lf("Connected in %.1f s · styles: %lld", Date().timeIntervalSince(started), styles.count)
        } catch {
            serverOK = false
            serverStatus = error.localizedDescription
        }
        testing = false
    }
}
