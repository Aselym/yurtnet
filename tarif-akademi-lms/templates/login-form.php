<?php
/**
 * Ozel giris formu sablonu.
 *
 * Bu dosya TLMS_Auth::render_login_form() tarafindan include edilir.
 * Kullanilabilir degiskenler: $error_code (string)
 *
 * Site genelinde zaten tanimli olan .card / .form-panel / .form-grid /
 * .form-field / .btn / .btn-primary siniflari kullanilarak sitenin
 * mevcut tasarim sistemiyle birebir uyum saglanir.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$error_messages = array(
	'empty'    => __( 'Kullanıcı adı ve şifre alanları boş bırakılamaz.', 'tarif-lms' ),
	'invalid'  => __( 'Kullanıcı adı veya şifre hatalı.', 'tarif-lms' ),
	'pending'  => __( 'Hesabınız henüz onaylanmadı. Moderatör onayı bekleniyor.', 'tarif-lms' ),
	'rejected' => __( 'Başvurunuz onaylanmadı. Detaylı bilgi için bizimle iletişime geçin.', 'tarif-lms' ),
	'norole'   => __( 'Bu hesapla giriş yapma yetkiniz bulunmuyor.', 'tarif-lms' ),
);

$error_text = isset( $error_messages[ $error_code ] ) ? $error_messages[ $error_code ] : '';
?>
<div class="tlms-auth-wrap">
	<div class="card tlms-auth-card">
		<div class="section-heading" style="text-align:center;margin-bottom:1.5rem;">
			<span class="eyebrow"><?php esc_html_e( 'Tarif Akademi Panel', 'tarif-lms' ); ?></span>
			<h1 style="font-size:1.6rem;margin-top:.5rem;"><?php esc_html_e( 'Giriş Yap', 'tarif-lms' ); ?></h1>
		</div>

		<?php if ( $error_text ) : ?>
			<div class="tlms-auth-error" role="alert">
				<?php echo esc_html( $error_text ); ?>
			</div>
		<?php endif; ?>

		<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" class="form-grid tlms-auth-form">
			<input type="hidden" name="action" value="tlms_login">
			<?php wp_nonce_field( TLMS_Auth::NONCE_ACTION, TLMS_Auth::NONCE_FIELD ); ?>

			<div class="form-field full">
				<label for="tlms-username"><?php esc_html_e( 'Kullanıcı Adı veya E-posta', 'tarif-lms' ); ?></label>
				<input type="text" id="tlms-username" name="tlms_username" required autocomplete="username">
			</div>

			<div class="form-field full">
				<label for="tlms-password"><?php esc_html_e( 'Şifre', 'tarif-lms' ); ?></label>
				<input type="password" id="tlms-password" name="tlms_password" required autocomplete="current-password">
			</div>

			<div class="form-field full tlms-auth-remember">
				<label>
					<input type="checkbox" name="tlms_remember" value="1">
					<?php esc_html_e( 'Beni hatırla', 'tarif-lms' ); ?>
				</label>
			</div>

			<button type="submit" class="btn btn-primary tlms-auth-submit"><?php esc_html_e( 'Giriş Yap', 'tarif-lms' ); ?></button>
		</form>
	</div>
</div>
