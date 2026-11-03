import SwiftUI

// The welcome flow: a six-page tour of what each part of SaySo does and how to use it (the splash with the
// pen-written logo is SplashView). Every illustration is a small mock drawn with SwiftUI (no bitmaps, no
// screenshots); all messages in them are made up. Each mock plays a short entrance when its page comes in, and
// shows its final state at once with Reduce Motion on.

/// The tour: Welcome, Chat, Styles, Keyboard, Back Tap, Settings. Skip at the top, Continue / Get started below.
struct WelcomeOnboarding: View {
    let onDone: () -> Void
    @State private var page = 0

    private let pages: [TourPage] = [
        TourPage(kicker: nil, icon: "sparkles",
                 title: "Writes like you.",
                 text: "Messages, emails, essays. In your own words, for whoever you're writing to."),
        TourPage(kicker: "Chat", icon: "bubble.left.and.text.bubble.right",
                 title: "Ask, rewrite, reply.",
                 text: "Pick Write, Rewrite or Reply and a format. 👎 tells it what to fix; it learns."),
        TourPage(kicker: "Styles", icon: "person.text.rectangle",
                 title: "Your voice, for each audience.",
                 text: "Add your chats, emails or essays so it learns your voice."),
        TourPage(kicker: "Keyboard", icon: "keyboard",
                 title: "✨ in any app.",
                 text: "Type a draft anywhere, tap ✨, pick a version."),
        TourPage(kicker: "Back Tap", icon: "hand.tap",
                 title: "Reply from a screenshot.",
                 text: "Double-tap the back of your iPhone on any chat, pick a reply, and it's copied."),
        TourPage(kicker: "Settings", icon: "gearshape",
                 title: "Three steps, one minute.",
                 text: "The Settings tab walks you through each one."),
    ]

    private var isLast: Bool { page == pages.count - 1 }

    var body: some View {
        ZStack {
            Theme.backdrop
            VStack(spacing: 16) {
                HStack {
                    // The welcome page shows the big logo itself.
                    LogoView().frame(width: 84).opacity(page == 0 ? 0 : 1)
                    Spacer()
                    Button("Skip", action: onDone)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.secondary)
                        .opacity(isLast ? 0 : 1)
                        .disabled(isLast)
                }
                .frame(height: 30)
                .animation(.easeInOut(duration: 0.2), value: page)
                TabView(selection: $page) {
                    ForEach(pages.indices, id: \.self) { index in
                        TourPageView(page: pages[index]) {
                            illustration(index)
                        }
                        .tag(index)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                PageDots(count: pages.count, current: page)
                Button {
                    if isLast { onDone() } else { withAnimation(.snappy) { page += 1 } }
                } label: {
                    HStack(spacing: 8) {
                        isLast ? Text("Get started") : Text("Continue")
                        Image(systemName: isLast ? "sparkles" : "arrow.right")
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 12)
        }
        // The pages are laid out to fit an iPhone 15/16 screen without scrolling; cap the text size so they still do.
        .dynamicTypeSize(...DynamicTypeSize.xLarge)
    }

    @ViewBuilder
    private func illustration(_ index: Int) -> some View {
        let active = page == index
        switch index {
        case 0: WelcomeMock(active: active)
        case 1: ChatMock(active: active)
        case 2: StylesMock(active: active)
        case 3: KeyboardMock(active: active)
        case 4: BackTapMock(active: active)
        default: ChecklistMock(active: active)
        }
    }
}

private struct TourPage {
    let kicker: LocalizedStringKey?
    let icon: String
    let title: LocalizedStringKey
    let text: LocalizedStringKey
}

/// One page: the mock on a glass panel, the section it is about, a headline and one line of how to use it.
private struct TourPageView<Illustration: View>: View {
    let page: TourPage
    let illustration: Illustration

    init(page: TourPage, @ViewBuilder illustration: () -> Illustration) {
        self.page = page
        self.illustration = illustration()
    }

    var body: some View {
        VStack(spacing: 22) {
            illustration
                .dynamicTypeSize(...DynamicTypeSize.large)  // a picture: its text stays at mock size
                .frame(maxWidth: .infinity)
                .frame(height: 300)
                .background(.regularMaterial, in: .rect(cornerRadius: 28, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 28, style: .continuous).stroke(Color.primary.opacity(0.06)))
                .clipShape(.rect(cornerRadius: 28, style: .continuous))
                .shadow(color: Theme.glow.opacity(0.25), radius: 20, y: 8)
            VStack(alignment: .leading, spacing: 8) {
                if let kicker = page.kicker {
                    Label(kicker, systemImage: page.icon)
                        .font(Theme.label(14))
                        .foregroundStyle(Color.accentColor)
                }
                Text(page.title)
                    .font(Theme.title(26))
                    .foregroundStyle(.primary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                    .fixedSize(horizontal: false, vertical: true)
                Text(page.text)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Spacer(minLength: 0)
        }
        .padding(.top, 6)
        .padding(.horizontal, 2)
    }
}

/// The active page is a long gradient capsule, the others small dots.
private struct PageDots: View {
    let count: Int
    let current: Int

    var body: some View {
        HStack(spacing: 7) {
            ForEach(0..<count, id: \.self) { index in
                Capsule()
                    .fill(index == current ? AnyShapeStyle(Theme.accentGradient) : AnyShapeStyle(Color.secondary.opacity(0.25)))
                    .frame(width: index == current ? 24 : 8, height: 8)
            }
        }
        .animation(.snappy, value: current)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Page \(current + 1) of \(count)")
    }
}

// MARK: - Entrance animation

/// Steps a mock through its entrance: `step` goes 0, 1, 2, … after each delay while the page is shown, and back to
/// 0 when it leaves, so swiping back replays it. With Reduce Motion the last step shows at once.
private struct StepPlayer: ViewModifier {
    @Binding var step: Int
    let active: Bool
    let delays: [Double]
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content.task(id: active) {
            guard active else {
                step = 0
                return
            }
            if reduceMotion {
                step = delays.count
                return
            }
            step = 0
            for delay in delays {
                try? await Task.sleep(for: .seconds(delay))
                if Task.isCancelled { return }
                withAnimation(.spring(duration: 0.5, bounce: 0.3)) { step += 1 }
            }
        }
    }
}

private extension View {
    func playSteps(_ step: Binding<Int>, active: Bool, delays: [Double]) -> some View {
        modifier(StepPlayer(step: step, active: active, delays: delays))
    }

    /// Fades and lifts a part in once its step has come.
    func appear(_ shown: Bool, from offset: CGFloat = 10, scale: CGFloat = 0.96) -> some View {
        self.opacity(shown ? 1 : 0)
            .offset(y: shown ? 0 : offset)
            .scaleEffect(shown ? 1 : scale)
    }
}

/// A small capsule with an icon, like the pickers in the app.
private struct MockChip: View {
    let title: LocalizedStringKey
    var icon: String? = nil
    var selected = false
    var menu = false

    var body: some View {
        HStack(spacing: 4) {
            if let icon { Image(systemName: icon).font(.system(size: 10, weight: .semibold)) }
            Text(title).font(.caption.weight(selected ? .semibold : .medium)).lineLimit(1)
            if menu { Image(systemName: "chevron.down").font(.system(size: 8, weight: .bold)) }
        }
        .padding(.horizontal, 9)
        .frame(height: 26)
        .foregroundStyle(selected ? Color.white : Color.primary)
        .background {
            if selected {
                Capsule().fill(Theme.accentGradient)
            } else {
                Capsule().fill(Color(.secondarySystemGroupedBackground))
            }
        }
        .overlay(Capsule().stroke(Color.primary.opacity(selected ? 0 : 0.08)))
    }
}

/// A tiny label pointing at a part of a mock: "Mode", "Format".
private struct Callout: View {
    let text: LocalizedStringKey
    var body: some View {
        HStack(spacing: 3) {
            Text(text)
            Image(systemName: "arrow.down").font(.system(size: 8, weight: .bold))
        }
        .font(.caption2.weight(.semibold))
        .foregroundStyle(Color.accentColor)
    }
}

// MARK: - 1. Welcome: the logo and the three kinds of text

private struct WelcomeMock: View {
    let active: Bool
    @State private var step = 0
    @State private var breathe = false

    var body: some View {
        ZStack {
            Circle()
                .fill(RadialGradient(colors: [Theme.glow.opacity(0.45), .clear], center: .center, startRadius: 0, endRadius: 150))
                .frame(width: 300, height: 300)
                .scaleEffect(breathe ? 1.08 : 0.9)
                .offset(y: -20)
            VStack(spacing: 26) {
                LogoView()
                    .frame(width: 200)
                    .appear(step >= 1, from: 0, scale: 0.85)
                HStack(spacing: 8) {
                    kind("Messages", icon: "bubble.left.fill", at: 2)
                    kind("Emails", icon: "envelope.fill", at: 3)
                    kind("Essays", icon: "doc.text.fill", at: 4)
                }
            }
        }
        .padding(18)
        .playSteps($step, active: active, delays: [0.15, 0.35, 0.15, 0.15])
        .onAppear {
            withAnimation(.easeInOut(duration: 2).repeatForever(autoreverses: true)) { breathe = true }
        }
    }

    private func kind(_ title: LocalizedStringKey, icon: String, at index: Int) -> some View {
        Label(title, systemImage: icon)
            .font(.caption.weight(.semibold))
            .lineLimit(1)
            .padding(.horizontal, 10)
            .frame(height: 30)
            .background(.thinMaterial, in: .capsule)
            .overlay(Capsule().stroke(Color.accentColor.opacity(0.25)))
            .foregroundStyle(Theme.navy)
            .appear(step >= index, from: 12)
    }
}

// MARK: - 2. Chat: a request, an answer in your voice, 👎 that teaches it

private struct ChatMock: View {
    let active: Bool
    @State private var step = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Mode and format pickers, as at the bottom of the Chat tab.
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Callout(text: "Mode")
                    Spacer()
                    Callout(text: "Format")
                }
                .padding(.horizontal, 4)
                HStack(spacing: 5) {
                    MockChip(title: "Write", icon: "square.and.pencil", selected: true)
                    MockChip(title: "Rewrite")
                    MockChip(title: "Reply")
                    Spacer(minLength: 0)
                    MockChip(title: "Message", icon: "bubble.left.fill", menu: true)
                }
            }

            // What you ask for.
            Text("Tell Mira I'm 20 min late")
                .font(.subheadline)
                .foregroundStyle(.white)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(Theme.accentGradient,
                            in: UnevenRoundedRectangle(topLeadingRadius: Theme.bubble, bottomLeadingRadius: Theme.bubble,
                                                       bottomTrailingRadius: 4, topTrailingRadius: Theme.bubble,
                                                       style: .continuous))
                .frame(maxWidth: .infinity, alignment: .trailing)
                .appear(step >= 1)

            // The answer, the way you'd say it, with the buttons under every answer.
            VStack(alignment: .leading, spacing: 6) {
                Label("In your voice", systemImage: "sparkles")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Color.accentColor)
                Text("omg sorry running 20 min late 🙈")
                    .font(.subheadline.weight(.medium))
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(Color(.secondarySystemGroupedBackground),
                                in: UnevenRoundedRectangle(topLeadingRadius: Theme.bubble, bottomLeadingRadius: 4,
                                                           bottomTrailingRadius: Theme.bubble, topTrailingRadius: Theme.bubble,
                                                           style: .continuous))
                    .overlay(UnevenRoundedRectangle(topLeadingRadius: Theme.bubble, bottomLeadingRadius: 4,
                                                    bottomTrailingRadius: Theme.bubble, topTrailingRadius: Theme.bubble,
                                                    style: .continuous)
                        .stroke(Color.primary.opacity(0.06)))
                HStack(spacing: 14) {
                    action("doc.on.doc")
                    action("hand.thumbsup")
                    action(step >= 3 ? "hand.thumbsdown.fill" : "hand.thumbsdown", highlighted: step >= 3)
                    action("pencil")
                }
                .padding(.leading, 6)
            }
            .appear(step >= 2)

            // 👎 → a reason → a rule it keeps.
            HStack(spacing: 6) {
                MockChip(title: "Not my words", selected: true)
                Image(systemName: "arrow.right").font(.caption2.weight(.bold)).foregroundStyle(.secondary)
                Label("Learned", systemImage: "sparkles")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.navy)
                    .padding(.horizontal, 9)
                    .frame(height: 26)
                    .background(Color.accentColor.opacity(0.14), in: .capsule)
                    .appear(step >= 5, from: 0, scale: 0.8)
            }
            .appear(step >= 4, from: 6)
            Spacer(minLength: 0)
        }
        .padding(16)
        .playSteps($step, active: active, delays: [0.3, 0.6, 0.8, 0.35, 0.5])
    }

    private func action(_ icon: String, highlighted: Bool = false) -> some View {
        Image(systemName: icon)
            .font(.footnote.weight(.semibold))
            .foregroundStyle(highlighted ? Color.accentColor : Color.secondary)
            .scaleEffect(highlighted ? 1.25 : 1)
            .symbolEffect(.bounce, value: highlighted)
    }
}

// MARK: - 3. Styles: kinds of text and audiences

private struct StylesMock: View {
    let active: Bool
    @State private var step = 0

    private let emailGradient = LinearGradient(colors: [Color(red: 0.12, green: 0.37, blue: 0.84), Theme.glow],
                                               startPoint: .bottomLeading, endPoint: .topTrailing)
    private let essayGradient = LinearGradient(colors: [Color(red: 0.043, green: 0.165, blue: 0.357), Color.accentColor],
                                               startPoint: .topLeading, endPoint: .bottomTrailing)

    var body: some View {
        VStack(spacing: 10) {
            HStack(spacing: 8) {
                kind("Messages", icon: "bubble.left.fill", fill: Theme.accentGradient, at: 1)
                kind("Emails", icon: "envelope.fill", fill: emailGradient, at: 1)
                kind("Essays", icon: "doc.text.fill", fill: essayGradient, at: 1)
            }
            Grid(horizontalSpacing: 8, verticalSpacing: 8) {
                GridRow {
                    audience("💞", "Partner", habit: "lowercase · emoji", value: 0.85, at: 2)
                    audience("🍻", "Friends", habit: "short · slang", value: 0.7, at: 2)
                }
                GridRow {
                    audience("🏠", "Family", habit: "longer · warm", value: 0.55, at: 3)
                    audience("🎩", "Elders", habit: "full stops · polite", value: 0.4, at: 3)
                }
            }
            Label("Add chats, emails or essays", systemImage: "plus")
                .font(.caption.weight(.semibold))
                .foregroundStyle(Color.accentColor)
                .frame(maxWidth: .infinity)
                .frame(height: 34)
                .background(Color.accentColor.opacity(0.08), in: .capsule)
                .overlay(Capsule().strokeBorder(Color.accentColor.opacity(0.5), style: StrokeStyle(lineWidth: 1.2, dash: [4, 3])))
                .appear(step >= 4, from: 8)
            Spacer(minLength: 0)
        }
        .padding(16)
        .playSteps($step, active: active, delays: [0.2, 0.35, 0.25, 0.35])
    }

    private func kind(_ title: LocalizedStringKey, icon: String, fill: LinearGradient, at index: Int) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.white)
                .frame(width: 30, height: 30)
                .background(fill, in: .rect(cornerRadius: 9, style: .continuous))
            Text(title)
                .font(.caption.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 62)
        .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: Theme.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.card, style: .continuous).stroke(Color.primary.opacity(0.06)))
        .appear(step >= index)
    }

    private func audience(_ emoji: String, _ name: LocalizedStringKey, habit: LocalizedStringKey,
                          value: Double, at index: Int) -> some View {
        let shown = step >= index
        return VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 5) {
                Text(emoji).font(.subheadline)
                Text(name).font(.caption.weight(.semibold)).lineLimit(1)
                Spacer(minLength: 0)
            }
            Text(habit)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.primary.opacity(0.07))
                    Capsule().fill(Theme.accentGradient)
                        .frame(width: proxy.size.width * CGFloat(shown ? value : 0))
                        .animation(.easeOut(duration: 0.9).delay(0.15), value: shown)
                }
            }
            .frame(height: 5)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: Theme.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.card, style: .continuous).stroke(Color.primary.opacity(0.06)))
        .appear(shown)
    }
}

// MARK: - 4. Keyboard: a draft, ✨, three versions, one picked

private struct KeyboardMock: View {
    let active: Bool
    @State private var step = 0

    private let rows = [10, 9, 7]
    private let versions: [LocalizedStringKey] = ["omw!! 10 min late sorry", "running late 🙈 be there soon",
                                                  "sorry sorry 10 more min"]
    private let picked = 1

    var body: some View {
        VStack(spacing: 12) {
            // The message field: the draft, then the version you picked.
            HStack(spacing: 6) {
                ZStack(alignment: .leading) {
                    Text("running late sorry").opacity(step >= 4 ? 0 : 1)
                    Text(versions[picked]).opacity(step >= 4 ? 1 : 0)
                }
                .font(.subheadline)
                .lineLimit(1)
                Capsule().fill(Color.accentColor).frame(width: 2, height: 18)
                Spacer(minLength: 0)
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title3)
                    .foregroundStyle(Color.accentColor)
            }
            .padding(.leading, 14).padding(.trailing, 6).padding(.vertical, 6)
            .background(Color(.secondarySystemGroupedBackground), in: .capsule)
            .overlay(Capsule().stroke(Color.primary.opacity(0.08)))

            VStack(spacing: 8) {
                // The top strip: audience, format, ✨.
                HStack(spacing: 5) {
                    MockChip(title: "Friends", icon: "person.2.fill")
                    MockChip(title: "Message", icon: "bubble.left.fill")
                    Spacer(minLength: 0)
                    sparkleKey
                }
                ZStack {
                    letters.opacity(step >= 2 ? 0 : 1)
                    versionList.opacity(step >= 2 ? 1 : 0)
                }
                .frame(height: 117)
            }
            .padding(10)
            .background {
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(LinearGradient(colors: [Theme.glow.opacity(0.12), Theme.glow.opacity(0.32)],
                                         startPoint: .top, endPoint: .bottom))
            }
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(Color.primary.opacity(0.06)))
            Spacer(minLength: 0)
        }
        .padding(18)
        .playSteps($step, active: active, delays: [0.6, 0.35, 0.8, 0.5])
    }

    private var letters: some View {
        VStack(spacing: 7) {
            ForEach(rows.indices, id: \.self) { row in
                HStack(spacing: 4) {
                    ForEach(0..<rows[row], id: \.self) { _ in key }
                }
                .padding(.horizontal, CGFloat(10 - rows[row]) * 6)
            }
            HStack(spacing: 4) {
                key.frame(width: 34)
                key
                key.frame(width: 50)
            }
        }
    }

    private var versionList: some View {
        VStack(spacing: 6) {
            ForEach(versions.indices, id: \.self) { index in
                let chosen = step >= 3 && index == picked
                HStack(spacing: 6) {
                    Text(versions[index])
                        .font(.caption.weight(chosen ? .semibold : .regular))
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    if chosen {
                        Image(systemName: "checkmark.circle.fill").font(.caption)
                    }
                }
                .foregroundStyle(chosen ? Color.white : Color.primary)
                .padding(.horizontal, 12)
                .frame(maxWidth: .infinity, minHeight: 34)
                .background {
                    if chosen {
                        RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Theme.accentGradient)
                    } else {
                        RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Color(.secondarySystemGroupedBackground))
                    }
                }
                .appear(step >= 2, from: 8)
                .animation(.spring(duration: 0.45, bounce: 0.3).delay(Double(index) * 0.07), value: step)
            }
        }
    }

    private var key: some View {
        RoundedRectangle(cornerRadius: 4, style: .continuous)
            .fill(Color(.secondarySystemGroupedBackground))
            .frame(height: 24)
            .shadow(color: Theme.navy.opacity(0.18), radius: 0, y: 1)
    }

    /// Glows, then is pressed on step 1.
    private var sparkleKey: some View {
        let pressed = step == 1
        return Image(systemName: "sparkles")
            .font(.subheadline.weight(.bold))
            .foregroundStyle(.white)
            .frame(width: 46, height: 26)
            .background(Theme.accentGradient, in: .capsule)
            .shadow(color: Color.accentColor.opacity(pressed ? 0.9 : 0.45), radius: pressed ? 14 : 6)
            .scaleEffect(pressed ? 0.88 : 1)
            .overlay(alignment: .bottomTrailing) {
                Image(systemName: "hand.point.up.left.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(.white)
                    .shadow(color: .black.opacity(0.25), radius: 2, y: 1)
                    .offset(x: 10, y: 16)
                    .opacity(step == 1 ? 1 : 0)
            }
    }
}

// MARK: - 5. Back Tap: double tap, three replies, Copied

private struct BackTapMock: View {
    let active: Bool
    @State private var step = 0

    private let replies: [LocalizedStringKey] = ["haha yes!! what time", "can't tonight 😩 tmrw?", "omw"]
    private let picked = 1

    private var taps: Int { min(step, 2) }

    var body: some View {
        HStack(spacing: 16) {
            VStack(spacing: 10) {
                phone
                Text("Double tap")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            Image(systemName: "chevron.right")
                .font(.caption.weight(.bold))
                .foregroundStyle(Color.accentColor.opacity(0.6))
                .appear(step >= 3, from: 0)
            VStack(alignment: .leading, spacing: 8) {
                Label("Replies", systemImage: "sparkles")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Color.accentColor)
                VStack(spacing: 0) {
                    ForEach(replies.indices, id: \.self) { index in
                        replyRow(index)
                        if index < replies.count - 1 { Divider().padding(.leading, 10) }
                    }
                }
                .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: Theme.card, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: Theme.card, style: .continuous).stroke(Color.primary.opacity(0.06)))
                Label("Copied", systemImage: "checkmark.circle.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .frame(height: 28)
                    .background(Theme.accentGradient, in: .capsule)
                    .shadow(color: Color.accentColor.opacity(0.35), radius: 8, y: 3)
                    .frame(maxWidth: .infinity)
                    .appear(step >= 4, from: 6, scale: 0.8)
            }
            .appear(step >= 3, from: 14)
        }
        .padding(18)
        .playSteps($step, active: active, delays: [0.6, 0.3, 0.7, 0.9])
    }

    /// The back of an iPhone: the camera bump, a finger and a ripple for each tap.
    private var phone: some View {
        RoundedRectangle(cornerRadius: 24, style: .continuous)
            .fill(LinearGradient(colors: [Color(white: 0.28), Color(white: 0.12)], startPoint: .topLeading, endPoint: .bottomTrailing))
            .frame(width: 92, height: 184)
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(Color.white.opacity(0.15), lineWidth: 1))
            .overlay(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(Color.white.opacity(0.12))
                    .frame(width: 38, height: 38)
                    .overlay(alignment: .topLeading) { lens.padding(5) }
                    .overlay(alignment: .bottomLeading) { lens.padding(5) }
                    .padding(8)
            }
            .overlay {
                ZStack {
                    TapRipple(taps: taps)
                    Image(systemName: "hand.point.up.left.fill")
                        .font(.system(size: 30))
                        .foregroundStyle(.white)
                        .symbolEffect(.bounce, value: taps)
                        .offset(x: 6, y: 18)
                }
                .offset(y: 12)
            }
            .shadow(color: Theme.navy.opacity(0.3), radius: 12, y: 6)
    }

    private var lens: some View {
        Circle()
            .fill(Color.black.opacity(0.7))
            .frame(width: 13, height: 13)
            .overlay(Circle().stroke(Color.white.opacity(0.2), lineWidth: 1))
    }

    private func replyRow(_ index: Int) -> some View {
        let chosen = step >= 4 && index == picked
        return HStack(spacing: 6) {
            Text(replies[index])
                .font(.caption)
                .lineLimit(1)
                .minimumScaleFactor(0.85)
            Spacer(minLength: 0)
            Image(systemName: chosen ? "checkmark" : "doc.on.doc")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(chosen ? Color.white : Color.secondary)
        }
        .foregroundStyle(chosen ? Color.white : Color.primary)
        .padding(.horizontal, 10)
        .frame(height: 36)
        .background {
            if chosen { Theme.accentGradient } else { Color.clear }
        }
    }
}

/// A ring that spreads out and fades each time `taps` goes up.
private struct TapRipple: View {
    let taps: Int

    private struct Wave {
        var scale = 0.4
        var opacity = 0.0
    }

    var body: some View {
        Circle()
            .stroke(Color.white, lineWidth: 2)
            .frame(width: 44, height: 44)
            .keyframeAnimator(initialValue: Wave(), trigger: taps) { content, wave in
                content.scaleEffect(wave.scale).opacity(wave.opacity)
            } keyframes: { _ in
                KeyframeTrack(\.scale) {
                    LinearKeyframe(0.4, duration: 0.01)
                    CubicKeyframe(1.7, duration: 0.55)
                }
                KeyframeTrack(\.opacity) {
                    LinearKeyframe(0.9, duration: 0.01)
                    LinearKeyframe(0, duration: 0.55)
                }
            }
    }
}

// MARK: - 6. Settings: what to set up

private struct ChecklistMock: View {
    let active: Bool
    @State private var step = 0

    var body: some View {
        VStack(spacing: 10) {
            row(1, icon: "keyboard", title: "Add the SaySo keyboard", detail: "Settings › General › Keyboard")
            row(2, icon: "lock.open.fill", title: "Allow Full Access", detail: "So ✨ can use your style")
            row(3, icon: "hand.tap.fill", title: "Turn on Back Tap", detail: "Double tap → replies")
            Spacer(minLength: 0)
        }
        .padding(16)
        .padding(.top, 8)
        .playSteps($step, active: active, delays: [0.3, 0.25, 0.25, 0.45, 0.35, 0.35])
    }

    /// Rows come in on steps 1–3 and get their check on steps 4–6.
    private func row(_ number: Int, icon: String, title: LocalizedStringKey, detail: LocalizedStringKey) -> some View {
        let done = step >= number + 3
        return HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .frame(width: 38, height: 38)
                .background(Theme.accentGradient, in: .rect(cornerRadius: 11, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(Theme.label(15))
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            Spacer(minLength: 0)
            Image(systemName: done ? "checkmark.circle.fill" : "circle")
                .font(.title3)
                .foregroundStyle(done ? Color.accentColor : Color.secondary.opacity(0.4))
                .contentTransition(.symbolEffect(.replace))
        }
        .padding(12)
        .frame(height: 70)
        .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: Theme.card + 2, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.card + 2, style: .continuous).stroke(Color.primary.opacity(0.06)))
        .appear(step >= number, from: 12)
    }
}
