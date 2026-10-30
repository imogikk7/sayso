import SwiftUI
import UIKit

/// SaySo keyboard: a panel, not a letter keyboard. The user types with their own keyboard, switches here,
/// and SaySo rewrites the draft, writes from an instruction, or offers replies, then inserts the result.
final class KeyboardViewController: UIInputViewController {
    private lazy var model = PanelModel(controller: self)

    override func viewDidLoad() {
        super.viewDidLoad()
        let host = UIHostingController(rootView: PanelView(model: model))
        host.view.backgroundColor = .clear
        host.sizingOptions = []
        addChild(host)
        view.addSubview(host.view)
        host.view.translatesAutoresizingMaskIntoConstraints = false
        let height = host.view.heightAnchor.constraint(equalToConstant: 250)
        height.priority = .defaultHigh  // lets the system resize during rotation without layout warnings
        NSLayoutConstraint.activate([
            host.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            host.view.topAnchor.constraint(equalTo: view.topAnchor),
            host.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            height,
        ])
        host.didMove(toParent: self)
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        model.showsGlobe = needsInputModeSwitchKey
        model.hasFullAccess = hasFullAccess
        model.readDraft()
    }

    override func textDidChange(_ textInput: UITextInput?) {
        model.readDraft()
    }
}
