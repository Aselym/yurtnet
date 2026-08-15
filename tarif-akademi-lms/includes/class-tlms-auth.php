<?php
/**
 * TLMS_Auth
 *
 * Sitenin standart wp-login.php ekranini devre disi birakip, [tarif_giris_formu]
 * kisa kodu ile herhangi bir sayfaya eklenebilen ozel bir giris formu sunar.
 * Basarili giristen sonra kullaniciyi roluyle eslesen panele yonlendirir.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class TLMS_Auth {

	const NONCE_ACTION = 'tlms_login_action';
	const NONCE_FIELD  = 'tlms_login_nonce';

	public function __construct() {
		add_shortcode( 'tarif_giris_formu', array( $this, 'render_login_form' ) );

		// Giris ve cikis islemleri hem oturum acmis hem acmamis kullanicilar
		// icin admin-post.php uzerinden calisir (nopriv_ eki gerekli).
		add_action( 'admin_post_nopriv_tlms_login', array( $this, 'handle_login' ) );
		add_action( 'admin_post_tlms_login', array( $this, 'handle_login' ) );
		add_action( 'admin_post_tlms_logout', array( $this, 'handle_logout' ) );

		// wp-login.php'nin varsayilan giris formunu ozel giris sayfamiza yonlendir.
		// Sifremi unuttum / sifre sifirlama gibi core akislari bozmamak icin
		// yalnizca "giris formunu goster" durumunu hedefliyoruz.
		add_action( 'login_init', array( $this, 'redirect_default_login_page' ) );

		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue_assets' ) );
	}

	/**
	 * Giris formu icin gerekli olan kucuk CSS dosyasini yukler.
	 * Sadece [tarif_giris_formu] kisa kodunu iceren sayfada calismasi
	 * yeterli oldugundan global olmasi performans acisindan sorun teskil
	 * etmez (dosya oldukca kucuk).
	 */
	public function enqueue_assets() {
		wp_enqueue_style(
			'tlms-auth',
			TLMS_PLUGIN_URL . 'assets/css/auth.css',
			array(),
			TLMS_VERSION
		);
	}

	/**
	 * [tarif_giris_formu] kisa kodunun ciktisini uretir.
	 *
	 * @return string
	 */
	public function render_login_form() {
		// Zaten giris yapmis bir kullanici bu sayfayi gorurse dogrudan
		// kendi paneline yonlendir; formu tekrar gostermeye gerek yok.
		if ( is_user_logged_in() ) {
			wp_safe_redirect( $this->get_redirect_url_for_user( wp_get_current_user() ) );
			exit;
		}

		$error_code = isset( $_GET['tlms_error'] ) ? sanitize_key( wp_unslash( $_GET['tlms_error'] ) ) : '';

		ob_start();
		include TLMS_PLUGIN_DIR . 'templates/login-form.php';
		return ob_get_clean();
	}

	/**
	 * admin-post.php uzerinden gelen giris denemesini isler.
	 * Basarili olursa kullaniciyi roluyle eslesen panele yonlendirir,
	 * basarisiz olursa (veya hesap onay bekliyorsa) hata koduyla
	 * giris sayfasina geri gonderir.
	 */
	public function handle_login() {
		check_admin_referer( self::NONCE_ACTION, self::NONCE_FIELD );

		$login_page_url = home_url( '/' . TLMS_LOGIN_PAGE_SLUG . '/' );

		$username = isset( $_POST['tlms_username'] ) ? sanitize_text_field( wp_unslash( $_POST['tlms_username'] ) ) : '';
		$password = isset( $_POST['tlms_password'] ) ? (string) wp_unslash( $_POST['tlms_password'] ) : '';

		if ( '' === $username || '' === $password ) {
			$this->redirect_with_error( $login_page_url, 'empty' );
		}

		$creds = array(
			'user_login'    => $username,
			'user_password' => $password,
			'remember'      => ! empty( $_POST['tlms_remember'] ),
		);

		$user = wp_signon( $creds, is_ssl() );

		if ( is_wp_error( $user ) ) {
			$this->redirect_with_error( $login_page_url, 'invalid' );
		}

		// Ogretmen hesabi henuz onaylanmamissa oturumu hemen kapat ve
		// duruma gore ayri bir hata mesaji goster.
		if ( TLMS_Roles::is_teacher( $user ) ) {
			$status = TLMS_Roles::get_status( $user );
			if ( 'active' !== $status ) {
				wp_logout();
				$this->redirect_with_error( $login_page_url, 'pending' === $status ? 'pending' : 'rejected' );
			}
		}

		// Sistemde taninan bir role sahip degilse (moderator/ogretmen/ogrenci
		// disinda kalan bir hesap) guvenlik geregi girisi reddet.
		if ( ! TLMS_Roles::is_moderator( $user ) && ! TLMS_Roles::is_teacher( $user ) && ! TLMS_Roles::is_student( $user ) ) {
			wp_logout();
			$this->redirect_with_error( $login_page_url, 'norole' );
		}

		wp_safe_redirect( $this->get_redirect_url_for_user( $user ) );
		exit;
	}

	/**
	 * Cikis (logout) islemini isler ve giris sayfasina geri yonlendirir.
	 */
	public function handle_logout() {
		check_admin_referer( 'tlms_logout_action', 'tlms_logout_nonce' );
		wp_logout();
		wp_safe_redirect( home_url( '/' . TLMS_LOGIN_PAGE_SLUG . '/' ) );
		exit;
	}

	/**
	 * wp-login.php?action=login (varsayilan giris formu goruntuleme)
	 * istegini ozel giris sayfamiza yonlendirir. Sifre sifirlama gibi
	 * diger core akislarina dokunmaz.
	 */
	public function redirect_default_login_page() {
		$action = isset( $_REQUEST['action'] ) ? sanitize_key( wp_unslash( $_REQUEST['action'] ) ) : 'login';

		$allowed_core_actions = array( 'lostpassword', 'resetpass', 'rp', 'logout', 'postpass' );
		if ( in_array( $action, $allowed_core_actions, true ) ) {
			return;
		}

		// POST ile buraya bir giris denemesi geliyorsa (ör. eski bir link/bot)
		// dokunma; sadece formu goruntuleme (GET) durumunu yonlendiriyoruz.
		if ( 'login' === $action && 'GET' === $_SERVER['REQUEST_METHOD'] ) {
			wp_safe_redirect( home_url( '/' . TLMS_LOGIN_PAGE_SLUG . '/' ) );
			exit;
		}
	}

	/**
	 * Kullanicinin rolune gore yonlendirilecegi panel URL'sini dondurur.
	 *
	 * @param WP_User $user
	 * @return string
	 */
	private function get_redirect_url_for_user( $user ) {
		if ( TLMS_Roles::is_moderator( $user ) ) {
			return admin_url();
		}
		if ( TLMS_Roles::is_teacher( $user ) ) {
			return home_url( '/' . TLMS_TEACHER_PANEL_SLUG . '/' );
		}
		if ( TLMS_Roles::is_student( $user ) ) {
			return home_url( '/' . TLMS_STUDENT_PANEL_SLUG . '/' );
		}
		return home_url( '/' );
	}

	/**
	 * Giris sayfasina belirli bir hata koduyla geri yonlendirir ve
	 * script'i sonlandirir.
	 *
	 * @param string $login_page_url
	 * @param string $error_code
	 */
	private function redirect_with_error( $login_page_url, $error_code ) {
		wp_safe_redirect( add_query_arg( 'tlms_error', $error_code, $login_page_url ) );
		exit;
	}
}
