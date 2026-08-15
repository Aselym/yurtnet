<?php
/**
 * Plugin Name:       Tarif Akademi LMS
 * Plugin URI:        https://tarifakademi.com
 * Description:       Ogrenci / Ogretmen / Moderator rolleri uzerinden calisan ozel egitim yonetim ve eslestirme sistemi. Adim 1: Roller, ozel tablolar, custom login ve role-based redirect.
 * Version:           1.0.0
 * Author:            Tarif Akademi
 * Text Domain:       tarif-lms
 * Requires at least: 6.0
 * Requires PHP:      7.4
 */

// Dogrudan erisimi engelle.
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// --------------------------------------------------------------------------
// Genel sabitler
// --------------------------------------------------------------------------
define( 'TLMS_VERSION', '1.0.0' );
define( 'TLMS_PLUGIN_FILE', __FILE__ );
define( 'TLMS_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'TLMS_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

// Panel sayfalarinin slug'lari. Bu slug'larla eslesen WP Page'ler
// sitede manuel olarak olusturulmali (Adim 4 / Adim 5'te icerikleri gelecek).
define( 'TLMS_STUDENT_PANEL_SLUG', 'ogrenci-paneli' );
define( 'TLMS_TEACHER_PANEL_SLUG', 'ogretmen-paneli' );

// Ozel giris formunun (shortcode) konuldugu sayfanin slug'i.
// wp-login.php'ye gelen tum trafik buraya yonlendirilir.
define( 'TLMS_LOGIN_PAGE_SLUG', 'giris' );

// --------------------------------------------------------------------------
// Bagimli siniflari yukle
// --------------------------------------------------------------------------
require_once TLMS_PLUGIN_DIR . 'includes/class-tlms-database.php';
require_once TLMS_PLUGIN_DIR . 'includes/class-tlms-roles.php';
require_once TLMS_PLUGIN_DIR . 'includes/class-tlms-auth.php';
require_once TLMS_PLUGIN_DIR . 'includes/class-tlms-activator.php';

// --------------------------------------------------------------------------
// Aktivasyon / Deaktivasyon kancalari
// --------------------------------------------------------------------------
register_activation_hook( __FILE__, array( 'TLMS_Activator', 'activate' ) );
register_deactivation_hook( __FILE__, array( 'TLMS_Activator', 'deactivate' ) );

// --------------------------------------------------------------------------
// Eklentiyi baslat
// --------------------------------------------------------------------------
add_action( 'plugins_loaded', 'tlms_bootstrap' );

/**
 * Eklentinin ana bilesenlerini ayaga kaldirir.
 * plugins_loaded'da calistirilir ki tum WP core fonksiyonlari (roller,
 * kullanici sistemi vb.) hazir olsun.
 */
function tlms_bootstrap() {
	// Roller ve yetki kontrolleri (admin bar gizleme, wp-admin engelleme).
	new TLMS_Roles();

	// Ozel giris formu shortcode'u + giris/cikis/yonlendirme mantigi.
	new TLMS_Auth();
}
