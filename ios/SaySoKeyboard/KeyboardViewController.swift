import SwiftUI
import UIKit

/// SaySo keyboard: its own letter keys with ✨ (the text in your style), or the panel (rewrite a draft typed with
/// another keyboard, write from an instruction, replies from the last screenshot or copied messages).
///
/// It sits like the stock keyboard: no background of its own (the system keyboard backdrop shows through the clear
/// input view), and the stock height: a 44 pt strip over 216 pt of keys in portrait, 38 + 160 in landscape.
final class KeyboardViewController: UIInputViewController {
    private lazy var model = PanelModel(controller: self)
    private var watch: Timer?  // picks up the Back Tap shortcut's replies while the keyboard is up
    private var height: NSLayoutConstraint?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear
        let host = UIHostingController(rootView: PanelView(model: model))
        host.view.backgroundColor = .clear
        host.sizingOptions = []
        host.safeAreaRegions = []  // the keys go to the bottom edge of the input view, as on the stock keyboard
        addChild(host)
        view.addSubview(host.view)
        host.view.translatesAutoresizingMaskIntoConstraints = false
        let height = view.heightAnchor.constraint(equalToConstant: currentMetrics.total)
        height.priority = .defaultHigh  // lets the system resize during rotation without layout warnings
        self.height = height
        NSLayoutConstraint.activate([
            host.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            host.view.topAnchor.constraint(equalTo: view.topAnchor),
            host.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            height,
        ])
        host.didMove(toParent: self)
        registerForTraitChanges([UITraitVerticalSizeClass.self]) { (self: Self, _: UITraitCollection) in
            self.updateHeight()
        }
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        matchFieldAppearance()
        updateHeight()
        model.appear(fullAccess: hasFullAccess, needsGlobe: needsInputModeSwitchKey)
        watch?.invalidate()
        watch = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.model.checkShortcutReplies() }
        }
    }

    override func textDidChange(_ textInput: UITextInput?) {
        matchFieldAppearance()
        model.fieldChanged()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        watch?.invalidate()
        model.flush()
    }

    /// Portrait or landscape sizes (an iPhone in landscape has a compact vertical size class).
    private var currentMetrics: KeyMetrics {
        KeyMetrics.current(compactHeight: traitCollection.verticalSizeClass == .compact)
    }

    private func updateHeight() {
        let total = currentMetrics.total
        if height?.constant != total { height?.constant = total }
    }

    /// A field that asks for a dark (or light) keyboard gets one, as with the stock keyboard; otherwise the system's
    /// light/dark setting applies. Key colors follow through SwiftUI's color scheme.
    private func matchFieldAppearance() {
        let style: UIUserInterfaceStyle
        switch textDocumentProxy.keyboardAppearance ?? .default {
        case .dark: style = .dark
        case .light: style = .light
        default: style = .unspecified
        }
        if view.overrideUserInterfaceStyle != style { view.overrideUserInterfaceStyle = style }
    }
}
