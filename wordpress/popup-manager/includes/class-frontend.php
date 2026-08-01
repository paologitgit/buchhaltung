<?php
/**
 * Auswahl und Ausgabe der Popups im Frontend.
 *
 * @package PopupManager
 */

namespace PopupManager;

defined( 'ABSPATH' ) || exit;

/**
 * Ermittelt die passenden Popups, lädt die Assets und gibt das Markup im
 * Footer aus.
 */
class Frontend {

	/**
	 * Popups, die auf dieser Seite ausgegeben werden.
	 *
	 * @var \WP_Post[]
	 */
	private $popups = array();

	/**
	 * Vorschaumodus aktiv.
	 *
	 * @var bool
	 */
	private $is_preview = false;

	/**
	 * Hooks registrieren.
	 */
	public function __construct() {
		add_action( 'wp_enqueue_scripts', array( $this, 'prepare' ) );
		// Priorität unter 20: WordPress gibt die Footer-Skripte bei 20 aus,
		// das Markup muss vorher im Dokument stehen.
		add_action( 'wp_footer', array( $this, 'render' ), 5 );
	}

	/**
	 * Passende Popups ermitteln und Assets einbinden.
	 *
	 * Läuft in `wp_enqueue_scripts`, weil dort die Conditional Tags wie
	 * `is_front_page()` bereits zuverlässig antworten.
	 *
	 * @return void
	 */
	public function prepare() {
		if ( is_admin() || is_feed() || is_embed() || is_preview() ) {
			return;
		}

		$this->popups = $this->find_popups();

		if ( empty( $this->popups ) ) {
			return;
		}

		wp_enqueue_style(
			'popup-manager',
			PM_PLUGIN_URL . 'assets/css/popup.css',
			array(),
			PM_VERSION
		);

		wp_enqueue_script(
			'popup-manager',
			PM_PLUGIN_URL . 'assets/js/popup.js',
			array(),
			PM_VERSION,
			true
		);

		$config = array();
		$css    = '';

		foreach ( $this->popups as $popup ) {
			$config[] = array(
				'id'            => (int) $popup->ID,
				'delay'         => (int) Plugin::meta( $popup->ID, 'delay' ),
				'autoClose'     => (int) Plugin::meta( $popup->ID, 'auto_close' ),
				'closeOverlay'  => (bool) Plugin::meta( $popup->ID, 'close_overlay' ),
				'closeButton'   => (bool) Plugin::meta( $popup->ID, 'close_button' ),
				'frequency'     => Plugin::meta( $popup->ID, 'frequency' ),
				'frequencyDays' => (int) Plugin::meta( $popup->ID, 'frequency_days' ),
			);

			$custom = Plugin::meta( $popup->ID, 'custom_css' );

			if ( $custom ) {
				$css .= "\n" . $custom;
			}
		}

		wp_localize_script(
			'popup-manager',
			'popupManagerData',
			array(
				'popups'    => $config,
				'isPreview' => $this->is_preview,
			)
		);

		if ( '' !== trim( $css ) ) {
			wp_add_inline_style( 'popup-manager', $css );
		}
	}

	/**
	 * Alle veröffentlichten Popups laden und nach ihren Regeln filtern.
	 *
	 * @return \WP_Post[]
	 */
	private function find_popups() {
		$preview_id = isset( $_GET['pm_preview'] ) ? absint( $_GET['pm_preview'] ) : 0; // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- Nur lesender Vorschaumodus, zusätzlich per Capability geschützt.

		if ( $preview_id && current_user_can( 'edit_post', $preview_id ) ) {
			$popup = get_post( $preview_id );

			if ( $popup && Plugin::POST_TYPE === $popup->post_type ) {
				$this->is_preview = true;

				return array( $popup );
			}
		}

		$popups = get_posts(
			array(
				'post_type'        => Plugin::POST_TYPE,
				'post_status'      => 'publish',
				'numberposts'      => 50,
				'orderby'          => 'menu_order date',
				'order'            => 'ASC',
				'suppress_filters' => false,
			)
		);

		return array_values( array_filter( $popups, array( $this, 'matches' ) ) );
	}

	/**
	 * Prüft, ob ein Popup auf der aktuellen Seite erscheinen soll.
	 *
	 * @param \WP_Post $popup Popup.
	 * @return bool
	 */
	private function matches( $popup ) {
		$where      = Plugin::meta( $popup->ID, 'where' );
		$current_id = $this->current_object_id();

		switch ( $where ) {
			case 'front':
				return is_front_page();

			case 'include':
				$ids = $this->id_list( Plugin::meta( $popup->ID, 'include_ids' ) );

				return $current_id && in_array( $current_id, $ids, true );

			case 'exclude':
				$ids = $this->id_list( Plugin::meta( $popup->ID, 'exclude_ids' ) );

				return ! ( $current_id && in_array( $current_id, $ids, true ) );

			case 'all':
			default:
				return true;
		}
	}

	/**
	 * ID des aktuell dargestellten Inhalts, sofern es einen gibt.
	 *
	 * @return int
	 */
	private function current_object_id() {
		if ( is_singular() ) {
			return (int) get_queried_object_id();
		}

		// Statische Startseite ohne is_singular()-Kontext (z. B. Blog-Seite).
		if ( is_front_page() && 'page' === get_option( 'show_on_front' ) ) {
			return (int) get_option( 'page_on_front' );
		}

		if ( is_home() && 'page' === get_option( 'show_on_front' ) ) {
			return (int) get_option( 'page_for_posts' );
		}

		return 0;
	}

	/**
	 * Kommagetrennte IDs in ein Integer-Array wandeln.
	 *
	 * @param string $value Rohwert aus dem Meta-Feld.
	 * @return int[]
	 */
	private function id_list( $value ) {
		return array_values( array_filter( array_map( 'absint', explode( ',', (string) $value ) ) ) );
	}

	/**
	 * Markup aller passenden Popups im Footer ausgeben.
	 *
	 * @return void
	 */
	public function render() {
		foreach ( $this->popups as $popup ) {
			$this->render_popup( $popup );
		}
	}

	/**
	 * Markup eines einzelnen Popups.
	 *
	 * @param \WP_Post $popup Popup.
	 * @return void
	 */
	private function render_popup( $popup ) {
		$width      = (int) Plugin::meta( $popup->ID, 'width' );
		$max_height = (int) Plugin::meta( $popup->ID, 'max_height' );

		$style = sprintf( '--pm-width:%dpx;', $width );

		if ( $max_height > 0 ) {
			$style .= sprintf( '--pm-max-height:%dpx;', $max_height );
		}

		$content = apply_filters( 'pm_popup_content', wpautop( do_shortcode( $popup->post_content ) ), $popup );
		$title   = get_the_title( $popup );
		?>
		<div class="pm-popup" id="pm-popup-<?php echo (int) $popup->ID; ?>"
			data-pm-id="<?php echo (int) $popup->ID; ?>" hidden>
			<div class="pm-popup__overlay" data-pm-overlay></div>
			<div class="pm-popup__box" role="dialog" aria-modal="true"
				aria-label="<?php echo esc_attr( $title ); ?>"
				style="<?php echo esc_attr( $style ); ?>">

				<?php if ( Plugin::meta( $popup->ID, 'close_button' ) ) : ?>
					<button type="button" class="pm-popup__close" data-pm-close
						aria-label="<?php esc_attr_e( 'Schliessen', 'popup-manager' ); ?>">
						<span aria-hidden="true">&times;</span>
					</button>
				<?php endif; ?>

				<div class="pm-popup__content">
					<?php
					// Inhalt aus dem Editor. WordPress filtert ihn bereits beim
					// Speichern (kses), deshalb hier wie bei Beitragsinhalten
					// unverändert ausgeben – sonst verschwinden z. B. Videos.
					echo $content; // phpcs:ignore WordPress.Security.EscapingOutput.OutputNotEscaped
					?>
				</div>
			</div>
		</div>
		<?php
	}
}
