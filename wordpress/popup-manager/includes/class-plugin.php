<?php
/**
 * Bootstrap des Plugins.
 *
 * @package PopupManager
 */

namespace PopupManager;

defined( 'ABSPATH' ) || exit;

/**
 * Lädt die Komponenten und kennt das Feld-Schema der Popups.
 */
final class Plugin {

	/**
	 * Post-Type-Slug der Popups.
	 */
	const POST_TYPE = 'pm_popup';

	/**
	 * Präfix aller Meta-Keys.
	 */
	const META_PREFIX = '_pm_';

	/**
	 * Singleton-Instanz.
	 *
	 * @var Plugin|null
	 */
	private static $instance = null;

	/**
	 * Liefert die Singleton-Instanz.
	 *
	 * @return Plugin
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}

		return self::$instance;
	}

	/**
	 * Registriert die Komponenten.
	 */
	private function __construct() {
		add_action( 'init', array( $this, 'load_textdomain' ) );

		new Post_Type();
		new Frontend();

		if ( is_admin() ) {
			new Meta_Boxes();
		}
	}

	/**
	 * Lädt die Übersetzungsdateien.
	 *
	 * @return void
	 */
	public function load_textdomain() {
		load_plugin_textdomain(
			'popup-manager',
			false,
			dirname( plugin_basename( PM_PLUGIN_FILE ) ) . '/languages'
		);
	}

	/**
	 * Schema aller Popup-Felder.
	 *
	 * Einzige Quelle für Defaults, Typen und das Speichern. Wer ein Feld
	 * ergänzen will, ergänzt es hier und im Meta-Box-Template.
	 *
	 * @return array<string, array>
	 */
	public static function fields() {
		return array(
			// Wo soll das Popup erscheinen.
			'where'          => array(
				'type'    => 'select',
				'default' => 'all',
				'options' => array( 'all', 'front', 'include', 'exclude' ),
			),
			'include_ids'    => array(
				'type'    => 'ids',
				'default' => '',
			),
			'exclude_ids'    => array(
				'type'    => 'ids',
				'default' => '',
			),

			// Zeitverhalten.
			'delay'          => array(
				'type'    => 'int',
				'default' => 0,
				'min'     => 0,
				'max'     => 600,
			),
			'auto_close'     => array(
				'type'    => 'int',
				'default' => 0,
				'min'     => 0,
				'max'     => 600,
			),
			'close_button'   => array(
				'type'    => 'bool',
				'default' => 1,
			),
			'close_overlay'  => array(
				'type'    => 'bool',
				'default' => 1,
			),

			// Häufigkeit.
			'frequency'      => array(
				'type'    => 'select',
				'default' => 'always',
				'options' => array( 'always', 'session', 'days' ),
			),
			'frequency_days' => array(
				'type'    => 'int',
				'default' => 7,
				'min'     => 1,
				'max'     => 365,
			),

			// Grösse.
			'width'          => array(
				'type'    => 'int',
				'default' => 600,
				'min'     => 200,
				'max'     => 2000,
			),
			'max_height'     => array(
				'type'    => 'int',
				'default' => 0,
				'min'     => 0,
				'max'     => 2000,
			),

			// Farben.
			'overlay_color'   => array(
				'type'    => 'color',
				'default' => '#000000',
			),
			'overlay_opacity' => array(
				'type'    => 'int',
				'default' => 60,
				'min'     => 0,
				'max'     => 100,
			),
			'box_bg_color'    => array(
				'type'    => 'color',
				'default' => '#ffffff',
			),
			'box_text_color'  => array(
				'type'    => 'color',
				'default' => '#1a1a1a',
			),

			// Gestaltung.
			'custom_css'     => array(
				'type'    => 'css',
				'default' => '',
			),
		);
	}

	/**
	 * Liest einen Popup-Meta-Wert inklusive Default und Typ-Cast.
	 *
	 * @param int    $popup_id Popup-ID.
	 * @param string $key      Feld-Key ohne Präfix.
	 * @return mixed
	 */
	public static function meta( $popup_id, $key ) {
		$fields = self::fields();

		if ( ! isset( $fields[ $key ] ) ) {
			return '';
		}

		$field = $fields[ $key ];
		$value = get_post_meta( $popup_id, self::META_PREFIX . $key, true );

		if ( '' === $value || null === $value ) {
			return $field['default'];
		}

		if ( 'int' === $field['type'] || 'bool' === $field['type'] ) {
			return (int) $value;
		}

		return $value;
	}

	/**
	 * Bereinigt einen Wert gemäss Feld-Schema.
	 *
	 * @param string $key   Feld-Key ohne Präfix.
	 * @param mixed  $value Rohwert aus dem Formular.
	 * @return mixed
	 */
	public static function sanitize( $key, $value ) {
		$fields = self::fields();

		if ( ! isset( $fields[ $key ] ) ) {
			return '';
		}

		$field = $fields[ $key ];

		switch ( $field['type'] ) {
			case 'int':
				$value = (int) $value;

				if ( isset( $field['min'] ) ) {
					$value = max( $field['min'], $value );
				}

				if ( isset( $field['max'] ) ) {
					$value = min( $field['max'], $value );
				}

				return $value;

			case 'bool':
				return empty( $value ) ? 0 : 1;

			case 'select':
				return in_array( $value, $field['options'], true ) ? $value : $field['default'];

			case 'color':
				$color = sanitize_hex_color( trim( (string) $value ) );

				return $color ? $color : $field['default'];

			case 'ids':
				$ids = array_filter( array_map( 'absint', preg_split( '/[^0-9]+/', (string) $value ) ) );

				return implode( ',', array_unique( $ids ) );

			case 'css':
				// Kein Markup im CSS-Feld, damit der <style>-Block nicht
				// verlassen werden kann.
				return trim( wp_strip_all_tags( (string) $value ) );

			default:
				return sanitize_text_field( (string) $value );
		}
	}

	/**
	 * Aktivierung: Post Type registrieren und Rewrite-Regeln neu schreiben.
	 *
	 * @return void
	 */
	public static function activate() {
		( new Post_Type() )->register();
		flush_rewrite_rules();
	}

	/**
	 * Deaktivierung: Rewrite-Regeln aufräumen.
	 *
	 * @return void
	 */
	public static function deactivate() {
		flush_rewrite_rules();
	}
}
