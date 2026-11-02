import SwiftUI
import UIKit

// Building blocks of the Keyboard and Set up tabs: gradient icon tiles, setting cards, step cards, a progress ring
// and the Back Tap flow. Everything sits on Theme.backdrop as glass cards.

/// Two-color fills for icon tiles, all in the SaySo blue family.
enum TileColors {
    static let sky: [Color] = [Color(red: 0.36, green: 0.62, blue: 1.0), Color(red: 0.23, green: 0.53, blue: 0.96)]
    static let deep: [Color] = [Color(red: 0.24, green: 0.45, blue: 0.95), Color(red: 0.12, green: 0.27, blue: 0.70)]
    static let teal: [Color] = [Color(red: 0.32, green: 0.80, blue: 0.92), Color(red: 0.14, green: 0.55, blue: 0.86)]
    static let violet: [Color] = [Color(red: 0.58, green: 0.55, blue: 1.0), Color(red: 0.34, green: 0.40, blue: 0.94)]
    static let green: [Color] = [Color(red: 0.30, green: 0.82, blue: 0.56), Color(red: 0.12, green: 0.64, blue: 0.42)]
}

/// A rounded square with a gradient and a white SF Symbol, like an app icon.
struct IconTile: View {
    let systemImage: String
    var colors: [Color] = TileColors.sky
    var size: CGFloat = 36

    var body: some View {
        Image(systemName: systemImage)
            .font(.system(size: size * 0.45, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(
                LinearGradient(colors: colors, startPoint: .topLeading, endPoint: .bottomTrailing),
                in: .rect(cornerRadius: Theme.card - 2)
            )
            .shadow(color: (colors.last ?? Color.accentColor).opacity(0.35), radius: 6, y: 3)
            .accessibilityHidden(true)
    }
}

/// Icon tile + title + one-line explanation, the top of every card.
struct CardHeader: View {
    let icon: String
    var colors: [Color] = TileColors.sky
    let title: String
    var subtitle: String? = nil

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            IconTile(systemImage: icon, colors: colors)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(Theme.label(16)).foregroundStyle(.primary)
                if let subtitle {
                    Text(subtitle)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
    }
}

/// A glass card with a header and any controls under it.
struct SettingsCard<Content: View>: View {
    let icon: String
    let colors: [Color]
    let title: String
    let subtitle: String?
    let content: Content

    init(icon: String, colors: [Color] = TileColors.sky, title: String, subtitle: String? = nil,
         @ViewBuilder content: () -> Content) {
        self.icon = icon
        self.colors = colors
        self.title = title
        self.subtitle = subtitle
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(icon: icon, colors: colors, title: title, subtitle: subtitle)
            content
        }
        .glassCard()
    }
}

/// A card for one on/off setting: header with a switch on the right, an optional note under it.
struct ToggleCard: View {
    let icon: String
    let colors: [Color]
    let title: String
    let subtitle: String
    @Binding var isOn: Bool
    let note: String?
    let noteIcon: String

    init(icon: String, colors: [Color] = TileColors.sky, title: String, subtitle: String, isOn: Binding<Bool>,
         note: String? = nil, noteIcon: String = "info.circle") {
        self.icon = icon
        self.colors = colors
        self.title = title
        self.subtitle = subtitle
        self._isOn = isOn
        self.note = note
        self.noteIcon = noteIcon
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 10) {
                CardHeader(icon: icon, colors: colors, title: title, subtitle: subtitle)
                Toggle(title, isOn: $isOn)
                    .labelsHidden()
                    .tint(Color.accentColor)
            }
            if let note {
                NoteBox(icon: noteIcon, text: note)
            }
        }
        .glassCard()
    }
}

/// A small tinted box with an icon: privacy notes, hints.
struct NoteBox: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Color.accentColor)
            Text(text)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(10)
        .background(Color.accentColor.opacity(0.07), in: .rect(cornerRadius: Theme.chip))
    }
}

/// A tappable tile that is on or off (an audience, a format, a mode).
struct SelectTile: View {
    let icon: String
    let title: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(selected ? Color.accentColor : Color.secondary)
                    .frame(width: 20)
                Text(title)
                    .font(.subheadline.weight(selected ? .semibold : .regular))
                    .foregroundStyle(.primary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Spacer(minLength: 4)
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.body)
                    .foregroundStyle(selected ? Color.accentColor : Color.secondary.opacity(0.5))
            }
            .padding(.horizontal, 12)
            .frame(maxWidth: .infinity, minHeight: 46)
            .background(selected ? Color.accentColor.opacity(0.12) : Color.primary.opacity(0.04),
                        in: .rect(cornerRadius: Theme.card))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.card)
                    .stroke(selected ? Color.accentColor.opacity(0.45) : Color.primary.opacity(0.06), lineWidth: 1)
            )
            .contentShape(.rect(cornerRadius: Theme.card))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .animation(.snappy(duration: 0.2), value: selected)
    }
}

/// A light, tinted secondary button (Open Shortcuts, Open Settings next to a primary action).
struct SoftButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Color.accentColor)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Color.accentColor.opacity(configuration.isPressed ? 0.2 : 0.12), in: .capsule)
    }
}

/// "Settings › General › Keyboard": where to tap in the iPhone's Settings, as one wrapping line.
struct PathLine: View {
    let steps: [String]
    var icon = "gearshape"

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Color.accentColor)
            Text(steps.joined(separator: "  ›  "))
                .font(.footnote.weight(.medium))
                .foregroundStyle(Theme.navy)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(Color.accentColor.opacity(0.08), in: .rect(cornerRadius: Theme.chip))
        .overlay(RoundedRectangle(cornerRadius: Theme.chip).stroke(Color.accentColor.opacity(0.15)))
    }
}

// MARK: - Set up

/// "2 of 4 done" as a ring in the brand stroke.
struct ProgressRing: View {
    let done: Int
    let total: Int
    var size: CGFloat = 96

    private var fraction: Double {
        total > 0 ? min(1, Double(done) / Double(total)) : 0
    }

    var body: some View {
        ZStack {
            Circle().fill(.regularMaterial)
            Circle().stroke(Color.accentColor.opacity(0.15), lineWidth: 9)
            Circle()
                .trim(from: 0, to: fraction)
                .stroke(Theme.stroke, style: StrokeStyle(lineWidth: 9, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(done)")
                    .font(Theme.display(28))
                    .foregroundStyle(Theme.navy)
                Text("of \(total) done")
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(.secondary)
            }
        }
        .frame(width: size, height: size)
        .shadow(color: Theme.glow.opacity(0.25), radius: 12, y: 4)
        .animation(.snappy, value: done)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(done) of \(total) steps done")
    }
}

/// The step number in a gradient circle; a green check once the step is done.
struct StepBadge: View {
    let number: Int
    let done: Bool

    private var fill: LinearGradient {
        LinearGradient(colors: done ? TileColors.green : TileColors.sky, startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    var body: some View {
        ZStack {
            Circle().fill(fill)
            if done {
                Image(systemName: "checkmark").font(.system(size: 15, weight: .heavy))
            } else {
                Text("\(number)").font(Theme.display(16))
            }
        }
        .foregroundStyle(.white)
        .frame(width: 36, height: 36)
        .shadow(color: (done ? Color.green : Color.accentColor).opacity(0.35), radius: 6, y: 3)
        .accessibilityHidden(true)
    }
}

/// "Done" in green or "To do" in gray.
struct StatusTag: View {
    let done: Bool

    var body: some View {
        Label(done ? "Done" : "To do", systemImage: done ? "checkmark" : "circle.dashed")
            .font(.caption.weight(.semibold))
            .labelStyle(.titleAndIcon)
            .padding(.horizontal, 9)
            .padding(.vertical, 4)
            .foregroundStyle(done ? Color.green : Color.secondary)
            .background((done ? Color.green : Color.primary).opacity(0.1), in: .capsule)
    }
}

/// One setup step: number, title, state, a line of explanation and its actions.
struct StepCard<Actions: View>: View {
    let number: Int
    let title: String
    let detail: String
    let done: Bool
    let actions: Actions

    init(number: Int, title: String, done: Bool, detail: String, @ViewBuilder actions: () -> Actions) {
        self.number = number
        self.title = title
        self.detail = detail
        self.done = done
        self.actions = actions()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 12) {
                StepBadge(number: number, done: done)
                Text(title)
                    .font(Theme.label(17))
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 6)
                StatusTag(done: done)
            }
            Text(detail)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            actions
        }
        .glassCard()
        .accessibilityElement(children: .contain)
    }
}

/// The Back Tap shortcut as a picture: double-tap → Take Screenshot → Reply from Screenshot → replies.
struct ShortcutFlow: View {
    var body: some View {
        VStack(spacing: 12) {
            HStack(spacing: 6) {
                Image(systemName: "hand.tap.fill")
                Text("Double-tap the back of your iPhone")
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Theme.stroke, in: .capsule)

            Image(systemName: "arrow.down")
                .font(.caption.weight(.bold))
                .foregroundStyle(.tertiary)

            HStack(alignment: .top, spacing: 2) {
                FlowNode(icon: "camera.viewfinder", title: "Take Screenshot", caption: "Shortcuts", highlighted: false)
                FlowArrow()
                FlowNode(icon: "sparkles", title: "Reply from Screenshot", caption: "SaySo", highlighted: true)
                FlowArrow()
                FlowNode(icon: "keyboard", title: "3 replies", caption: "in your keyboard", highlighted: false)
            }
        }
        .padding(.vertical, 14)
        .padding(.horizontal, 8)
        .frame(maxWidth: .infinity)
        .background(Color.accentColor.opacity(0.06), in: .rect(cornerRadius: Theme.card))
        .overlay(RoundedRectangle(cornerRadius: Theme.card).stroke(Color.accentColor.opacity(0.12)))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Double-tap the back of your iPhone, the shortcut takes a screenshot, SaySo replies from it, you get three replies and the first one is copied.")
    }
}

struct FlowNode: View {
    let icon: String
    let title: String
    let caption: String
    let highlighted: Bool

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 19, weight: .semibold))
                .foregroundStyle(highlighted ? Color.white : Color.accentColor)
                .frame(width: 46, height: 46)
                .background {
                    if highlighted {
                        RoundedRectangle(cornerRadius: Theme.card).fill(Theme.accentGradient)
                    } else {
                        RoundedRectangle(cornerRadius: Theme.card).fill(.regularMaterial)
                    }
                }
                .overlay(RoundedRectangle(cornerRadius: Theme.card).stroke(Color.primary.opacity(highlighted ? 0 : 0.08)))
                .shadow(color: Color.accentColor.opacity(highlighted ? 0.4 : 0.1), radius: 6, y: 3)
            Text(title)
                .font(.caption.weight(.semibold))
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.85)
                .fixedSize(horizontal: false, vertical: true)
            Text(caption)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
        }
        .frame(maxWidth: .infinity)
    }
}

struct FlowArrow: View {
    var body: some View {
        Image(systemName: "chevron.right")
            .font(.caption.weight(.heavy))
            .foregroundStyle(Color.accentColor.opacity(0.6))
            .padding(.top, 16)
    }
}

/// The last screenshot's replies as tappable bubbles; tap copies one.
struct LastRepliesCard: View {
    let response: ReplyResponse
    @State private var copied: Int?

    private var subtitle: String {
        if let audience = Audience(rawValue: response.context.audience) {
            return "For \(audience.label) · tap one to copy it."
        }
        return "Tap one to copy it."
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            CardHeader(icon: "text.bubble.fill", colors: TileColors.teal, title: "Last screenshot replies", subtitle: subtitle)
            ForEach(Array(response.replies.enumerated()), id: \.offset) { index, reply in
                row(index: index, text: reply.text)
            }
        }
        .glassCard()
    }

    private func row(index: Int, text: String) -> some View {
        let isCopied = copied == index
        return Button {
            UIPasteboard.general.string = text
            copied = index
        } label: {
            HStack(alignment: .top, spacing: 10) {
                Text(text)
                    .font(.subheadline)
                    .foregroundStyle(.primary)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: isCopied ? "checkmark.circle.fill" : "doc.on.doc")
                    .foregroundStyle(isCopied ? Color.green : Color.accentColor)
            }
            .padding(12)
            .background(Color.accentColor.opacity(0.07), in: .rect(cornerRadius: Theme.bubble))
            .overlay(RoundedRectangle(cornerRadius: Theme.bubble).stroke(Color.accentColor.opacity(isCopied ? 0.4 : 0.1)))
            .contentShape(.rect(cornerRadius: Theme.bubble))
        }
        .buttonStyle(.plain)
        .accessibilityHint(isCopied ? "Copied" : "Copies this reply")
    }
}
