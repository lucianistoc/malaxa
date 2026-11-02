<?php

namespace modules\malaxa\console\controllers;

use Craft;
use craft\console\Controller;
use craft\elements\Asset;
use craft\elements\Entry;
use craft\elements\GlobalSet;
use craft\helpers\Json;
use craft\helpers\StringHelper;
use yii\console\ExitCode;

/**
 * Imports the hospital's content from the static site's data files into Craft.
 *
 *     php craft index-assets/one uploads     # first: register the files in uploads/ as assets
 *     php craft malaxa/import                # then: globals, prices, specialties, doctors, news, documents, pages
 *
 * Reads ../site.config.json and ../content/*.json (the repository root). Entries are
 * matched by slug, so re-running updates them instead of creating duplicates.
 */
class ImportController extends Controller
{
    /** @var string Directory holding site.config.json and content/ */
    public string $source = '';

    private array $cfg = [];
    private array $lists = [];
    /** @var array<string, int> slug => entry id, per section */
    private array $ids = [];

    public function options($actionID): array
    {
        return array_merge(parent::options($actionID), ['source']);
    }

    public function actionIndex(): int
    {
        $src = rtrim($this->source ?: dirname(Craft::getAlias('@root')), '/');
        $this->cfg = Json::decode(file_get_contents("$src/site.config.json"));
        $this->lists = Json::decode(file_get_contents("$src/content/lists.json"));
        $specs = Json::decode(file_get_contents("$src/content/specialties.json"));
        $docs = Json::decode(file_get_contents("$src/content/doctors.json"));
        $news = Json::decode(file_get_contents("$src/content/news.json"));

        $this->importGlobals();
        $this->importPriceGroups();
        $this->importSpecialties($specs);
        $this->importDoctors($docs);
        $this->importNews($news);
        $this->importPages();
        $this->importDocumentGroups();
        $this->importHomepage();

        $this->stdout("Import done.\n");
        return ExitCode::OK;
    }

    // ------------------------------------------------------------------ globals

    private function importGlobals(): void
    {
        $c = $this->cfg;
        $k = $c['contact'];
        $set = GlobalSet::find()->handle('siteSettings')->one();
        $set->setFieldValues([
            'legalName' => $c['legal_name'], 'tagline' => $c['tagline'], 'logoText' => $c['logo_text'], 'logoSubtext' => $c['logo_subtext'],
            'logoIcon' => $this->assetIds([$c['logo_icon'] ?? null]), 'badgeImage' => $this->assetIds([$c['accreditation_image'] ?? null]),
            'founded' => $c['founded'], 'heroTitle' => $c['hero_title'], 'heroSubtitle' => $c['hero_subtitle'],
            'heroImage' => $this->assetIds([$c['hero_image'] ?? null]),
            'stats' => $this->rows(array_map(fn($s) => [$s['value'], $s['label']], $c['stats'])),
            'phone' => $k['phone'], 'phoneAppointments' => $k['phone_appointments'] ?? '', 'fax' => $k['fax'] ?? '', 'phoneHr' => $k['phone_hr'] ?? '',
            'email' => $k['email'], 'emailOffice' => $k['email_office'] ?? '', 'emailIntegrity' => $k['email_integrity'] ?? '',
            'spokesperson' => $k['spokesperson'] ?? '', 'address' => $k['address'], 'addressShort' => $k['address_short'], 'mapQuery' => $k['map_query'],
            'bookingUrl' => $k['online_booking'] ?? '', 'feedbackUrl' => $c['feedback_url'] ?? '',
            'audiences' => $this->rows(array_map(fn($x) => [trim($x)], explode('·', $k['audiente']))),
            'transport' => $this->rows(array_map(fn($label, $text) => [ucfirst($label), $text, ['metrou' => 'metro', 'tramvai' => 'tram'][$label] ?? 'bus'], array_keys($c['transport']), $c['transport'])),
            'visiting' => $this->rows($c['visiting'] ?? []),
            'visitingPdf' => $this->assetIds([$c['visiting_pdf'] ?? null]),
            'socialLinks' => $this->rows(array_map(fn($n, $u) => [$n, $u], array_keys(array_filter($c['social'])), array_filter($c['social']))),
            'externalLinks' => $this->rows($c['external_links'] ?? []),
            'colorPrimary' => $c['colors']['primary'], 'colorPrimaryDark' => $c['colors']['primary_dark'], 'colorAccent' => $c['colors']['accent'],
            'colorAccentDark' => $c['colors']['accent_dark'], 'colorHighlight' => $c['colors']['highlight'], 'colorSoft' => $c['colors']['soft'],
        ]);
        $this->save($set, 'globals');
    }

    // ------------------------------------------------------------------ data sections

    private function importPriceGroups(): void
    {
        foreach ($this->lists['prices'] as $g) {
            $this->upsert('priceGroups', 'priceGroup', StringHelper::slugify($g['group']), $g['group'], [
                'priceItems' => $this->rows($g['items']),
            ]);
        }
    }

    private function importSpecialties(array $specs): void
    {
        foreach ($specs as $s) {
            $blocks = [];
            foreach ($s['sections'] ?? [] as $sec) {
                if (!empty($sec['accordion'])) {
                    $blocks[] = $this->bAccordion($sec['title'] ?? '', array_map(fn($x) => [$x['q'], implode("\n", $x['a'])], $sec['accordion']));
                    continue;
                }
                if (!empty($sec['text'])) {
                    $blocks[] = $this->bText($sec['title'] ?? '', $this->html($sec['text']));
                    if (!empty($sec['items'])) {
                        $blocks[] = $this->bList('', $sec['items']);
                    }
                } elseif (!empty($sec['items'])) {
                    $blocks[] = $this->bList($sec['title'] ?? '', $sec['items']);
                }
            }
            $a = $s['amb'] ?? [];
            $priceGroupId = $this->ids['priceGroups'][StringHelper::slugify($s['price_group'] ?? '')] ?? null;
            $this->upsert('specialties', 'specialty', $s['slug'], $s['name'], [
                'iconName' => $s['icon'], 'summary' => $s['summary'], 'beds' => $s['beds'] ?? '',
                'body' => $this->html($s['intro'] ?? []),
                'contentBlocks' => $this->blocks($blocks),
                'equipment' => $this->rows(array_map(fn($x) => [ucfirst($x)], $s['equipment'] ?? [])),
                'gallery' => $this->assetIds($s['gallery'] ?? []),
                'hours' => $this->rows(array_map(fn($x) => [$x], $s['hours'] ?? [])),
                'phones' => $this->rows(array_map(fn($x) => [$x], $s['phone'] ?? [])),
                'docLinks' => $this->rows($s['links'] ?? []),
                'hasAmbulatory' => !empty($s['ambulatoriu']), 'ambulatoryOnly' => !empty($s['ambulatoriu_only']),
                'ambIntro' => implode("\n\n", $a['intro'] ?? []),
                'ambProgram' => $this->rows(array_map(fn($x) => [$x], $a['program'] ?? [])),
                'ambPhones' => $this->rows(array_map(fn($x) => [$x], $a['phone'] ?? [])),
                'ambSchedule' => $this->rows($a['schedule'] ?? []),
                'ambServices' => $this->rows(array_map(fn($x) => [$x], $a['services'] ?? [])),
                'priceGroup' => $priceGroupId ? [$priceGroupId] : [],
            ]);
        }
    }

    private function importDoctors(array $docs): void
    {
        foreach ($docs as $d) {
            $this->upsert('doctors', 'doctor', $d['slug'], $d['name'], [
                'specialty' => [$this->ids['specialties'][$d['specialty']]],
                'grade' => $d['grade'], 'role' => $d['role'] ?? '', 'bio' => $d['bio'] ?? '',
                'photo' => $this->assetIds([$d['photo'] ?? null]),
            ]);
        }
    }

    private function importNews(array $news): void
    {
        $t = time();
        foreach ($news as $i => $n) {
            $e = $this->upsert('news', 'newsItem', $n['slug'], $n['title'], [
                'category' => $n['category'], 'excerpt' => $n['excerpt'], 'showDate' => !empty($n['date']),
                'image' => $this->assetIds([$n['image'] ?? null]),
                'body' => $this->html($n['body']),
                'attachment' => $this->assetIds([$n['attachment'] ?? null]),
                'linkUrl' => $n['link'] ?? '',
            ], function(Entry $e) use ($n, $t, $i) {
                // Keep the source order: newest first, one minute apart when there is no date.
                $e->postDate = !empty($n['date']) ? new \DateTime($n['date']) : (new \DateTime())->setTimestamp($t - $i * 60);
            });
        }
    }

    private function importDocumentGroups(): void
    {
        $pageFor = ['echipa-de-management/' => 'echipa-de-management', 'program-garzi/' => 'program-garzi', 'acreditari/' => 'acreditari'];
        foreach ($this->lists['public_interest'] as $p) {
            [$assets, $links] = $this->splitDocs($p['docs'] ?? []);
            $linked = isset($p['page']) ? ($this->ids['pages'][$pageFor[$p['page']] ?? rtrim($p['page'], '/')] ?? null) : null;
            $this->upsert('documentGroups', 'documentGroup', StringHelper::slugify($p['title']), $p['title'], [
                'iconName' => $p['icon'], 'note' => $p['note'] ?? '', 'documents' => $assets, 'docLinks' => $this->rows($links),
                'linkedPage' => $linked ? [$linked] : [], 'linkUrl' => $p['link'] ?? '',
            ]);
        }
    }

    private function importHomepage(): void
    {
        $home = Entry::find()->section('homepage')->one();
        $home->setFieldValues([
            'heading' => 'Un spital cu tradiție, construit în jurul pacientului.',
            'body' => '<p>Înființat în 1963 ca policlinică a platformei industriale „23 August”, spitalul poartă din 1991 numele industriașului Nicolae Malaxa. Astăzi are 263 de paturi, secții clinice universitare, ambulatoriu integrat de specialitate și linii de gardă non-stop.</p>',
            'image' => $this->assetIds([$this->cfg['hero_image'] ?? null]),
            'cardItems' => $this->rows([
                ['Spital acreditat', 'Acreditat ANMCS, certificat ISO 9001, laborator acreditat RENAR (ISO 15189).', 'award', ''],
                ['Clinici universitare', 'Secții clinice în colaborare cu UMF „Carol Davila”, cu activitate de cercetare și studii clinice.', 'people', ''],
                ['Gardă non-stop', 'Linii de gardă 24/24 h pentru obstetrică-ginecologie, neonatologie, diabet, medicină internă, chirurgie, ATI și laborator.', 'ambulance', ''],
                ['Aparatură modernă', 'Computer tomograf multislice, mamograf digital, laparoscopie, facoemulsificare și bază de recuperare completă.', 'cpu', ''],
            ]),
        ]);
        $this->save($home, 'homepage');
    }

    // ------------------------------------------------------------------ pages

    private function importPages(): void
    {
        $L = $this->lists;
        $k = $this->cfg['contact'];
        $docsReq = ['Bilet de trimitere de la medicul de familie / medic specialist în contract cu casa de asigurări', 'Cardul de sănătate', 'Dovada calității de asigurat', 'CI / BI / Pașaport / Certificat de naștere, original și xerocopie'];

        // [slug, title, type, parent slug, heading, intro html, blocks, hideFromNav, navGroup]
        $pages = [
            ['despre-noi', 'Despre noi', 'page', null, 'Scurt istoric', '', [
                $this->bMedia('Nicolae Malaxa', $this->html(['Nicolae Malaxa, un industriaș vizionar, născut la Huși, inginer format la Politehnica din Karlsruhe, în Germania, înființează în 1921 un atelier pentru fabricat material rulant și pentru reparat locomotive și vagoane. În perioada 1923–1927 construiește o uzină lângă Halta Titan. Patru ani mai târziu, industriașul român încheie un contract cu societatea Căile Ferate Române pentru fabricarea unor locomotive de concepție proprie românească.']), 'uploads/images/nicolae-malaxa.jpg'),
                $this->bMedia('De la Policlinica „23 August” la Spitalul Clinic „Nicolae Malaxa”', $this->html([
                    'Înființată în anul 1963, Policlinica „23 August” deservea întreaga platformă industrială „23 August”. În anul 1991 denumirea de Spitalul de Întreprindere „23 August” a fost schimbată în actuala denumire, Spitalul Clinic „Nicolae Malaxa”.',
                    'În perioada 2007–2008 spitalul a intrat în consolidare, reamenajare și dotare, lucrările finalizându-se în anul 2010.',
                    'Din 2011 a preluat în atribuțiile și responsabilitățile sale o parte din Spitalul Clinic Caritas – Acad. Prof. Dr. „Nicolae Cajal” (obstetrică-ginecologie, neonatologie, chirurgie, ATI, anatomie patologică), ca urmare a desființării acestuia.',
                ]), 'uploads/images/locomotiva.jpg'),
                $this->bCards('Valorile noastre', array_map(fn($v, $i) => [$v['title'], $v['text'], $i, ''], $L['values'], ['hands', 'award', 'cpu', 'check'])),
            ]],
            ['structura-organizatorica', 'Structura organizatorică', 'page', 'despre-noi', '', '', [
                $this->bTable('Structura organizatorică', ['Secție / compartiment', 'Paturi'], $L['structure']),
                $this->bText('', $this->html(['Pe lângă secțiile cu paturi, spitalul are ambulatoriu integrat de specialitate, laborator de analize medicale, laborator de radiologie și imagistică medicală, serviciu de anatomie patologică, cameră de gardă și farmacie.'])),
                $this->bDocs('', [['Organigrama Spitalului Clinic „Nicolae Malaxa” (PDF)', 'uploads/docs/files/organigrama-sp-malaxa.pdf']]),
            ]],
            ['echipa-de-management', 'Echipa managerială', 'page', 'despre-noi', '', '', [
                $this->bCards('Comitetul director', array_map(fn($m) => [$m['name'], $m['role'] . (isset($m['audiente']) ? "\nAudiențe: " . $m['audiente'] : ''), 'user', ''], $L['management'])),
                $this->bList('Consiliul de administrație', $L['board'][0]['members']),
                $this->bDocs('', [$L['board_doc']]),
                $this->bList('Consiliul etic', $L['ethics']),
                $this->bDocs('', [['Anuarul consiliului etic – 2020', 'uploads/docs/files/Anuarul Etic-2020.pdf'], ['Raportul consiliului etic – Sem. 2 2020', 'uploads/docs/files/Raport Consiliul Etic-s2.2020.pdf']]),
            ]],
            ['acreditari', 'Acreditări / Certificări', 'page', 'despre-noi', '', '', [
                $this->bDocs('Acreditări și certificări', array_map(fn($a) => [$a['title'], $a['url']], $L['accreditations'])),
                $this->bText('', $this->html(['Laboratorul de analize medicale este acreditat RENAR conform ISO 15189:2013 pentru hematologie, chimie clinică, imunologie și parazitologie.'])),
            ]],
            ['indicatori-de-calitate', 'Indicatori și statistici', 'page', 'despre-noi', '', '', [
                $this->bTable('Indicatori de activitate', ['Indicator', '2015', '2016'], $L['statistics']),
                $this->bDocs('Date și informații referitoare la activitatea spitalului (Ordinul 1117/2025)', [['Date și informații referitoare la activitatea spitalului (PDF)', 'uploads/docs/files/2026/date si informatii referitoare la activitatea spitalului.pdf']]),
                $this->bText('Acreditări', $this->html(['Spitalul este acreditat ANMCS și certificat ISO 9001; laboratorul de analize medicale este acreditat RENAR.'])),
            ]],
            ['noutati', 'Noutăți și campanii', 'newsIndex', 'despre-noi', '', '', []],
            ['cercetare-si-inovare', 'Cercetare și proiecte', 'page', 'despre-noi', '', '', [
                $this->bCards('Activități de cercetare', array_map(fn($r) => [$r[0], $r[1], 'microscope', ''], $L['research'])),
                $this->bDocs('Programe și proiecte', [['Programul Național de Diabet Zaharat', 'http://www.cnas.ro/page/programul-national-de-diabet-zaharat.html'], ['Îngrijiri la domiciliu – furnizori în contract cu CASMB', 'http://www.cnas.ro/casmb/page/lista-furnizori-in-contract.html'], ['Listă cabinete de medicină de familie', 'http://www.cnas.ro/casmb/page/lista-cabinete-medicina-de-familie.html']]),
            ]],
            ['parteneriate', 'Parteneriate', 'page', 'despre-noi', '', '', [
                $this->bCards('', array_map(fn($p) => [$p[0], $p[1], 'handshake', $p[2]], $L['partners'])),
            ]],
            ['cariere', 'Cariere', 'page', 'despre-noi', 'Alătură-te echipei noastre!', $this->html(['Posturile vacante sunt scoase la concurs conform legislației în vigoare. Anunțurile de concurs, centralizatoarele cu rezultatele fiecărei probe și rezultatele finale sunt publicate pe această pagină.']), [
                $this->bCards('', [['Concursuri / examene – Serviciul R.U.N.O.S.', ($k['phone_hr'] ?? '') . "\nLuni – Vineri, 08:00 – 16:00", 'phone', 'tel:' . preg_replace('/\D/', '', $k['phone_hr'] ?? '')]]),
                $this->bDocs('Concursuri și examene', array_map(fn($c) => [$c['title'], $c['url']], $L['contests'])),
            ]],
            ['specialitati-medicale', 'Specialități medicale', 'specialtiesIndex', null, '', '', []],
            ['centre-de-excelenta', 'Centre de excelență', 'page', 'specialitati-medicale', '', '', [
                $this->bCards('', [
                    ['Centrul de Diabet, Nutriție și Boli Metabolice', 'Secție clinică cu 45 de paturi, spitalizare de zi și cabinete de ambulatoriu cu program zilnic; derulează Programul Național de Sănătate – Diabet.', 'drop', 'service/diabet/'],
                    ['Clinica universitară de Alergologie și Imunologie', 'Clinică universitară a UMF „Carol Davila”, cu Laborator de Imunologie Clinică și testare alergologică in vivo și in vitro.', 'flask', 'service/alergologie/'],
                    ['Laborator de analize medicale acreditat RENAR', 'Acreditat conform ISO 15189:2013 pentru hematologie, chimie clinică, imunologie și parazitologie.', 'microscope', 'service/laborator/'],
                    ['Secția Clinică Obstetrică-Ginecologie', '50 de paturi, 2 săli de naștere, laparoscopie STORZ și nucleu de cercetare cu studii clinice în desfășurare.', 'female', 'service/obstetrica-ginecologie/'],
                ]),
            ], true],
            ['ambulatoriu', 'Ambulatoriu', 'ambulatoryIndex', null, 'Ambulatoriul integrat de specialitate', $this->html(['Consultații de specialitate fără internare. Pentru serviciile decontate de CASMB sunt necesare biletul de trimitere, cardul de sănătate, dovada calității de asigurat și actul de identitate.']), []],
            ['team', 'Medici', 'doctorsIndex', null, '', '', []],
            ['informatii-utile', 'Informații utile', 'page', null, '', '', [
                $this->bCards('Pentru pacienți', [
                    ['Internare și externare', '', 'clipboard', 'internare-si-externare/'], ['Servicii decontate prin CASMB', '', 'check', 'servicii-decontate-prin-cas/'],
                    ['Tarife servicii medicale', '', 'money', 'servicii-medicale-cu-plata/'], ['Drepturile și obligațiile pacienților', '', 'shield', 'drepturile-pacientilor/'],
                    ['Program gărzi spital', '', 'ambulance', 'program-garzi/'], ['Campanii de sănătate', '', 'award', 'educatie-pentru-sanatate/'],
                    ['Chestionar de feedback', '', 'chat', 'chestionar-de-feedback/'], ['Întrebări frecvente', '', 'clipboard', 'intrebari-frecvente/'],
                ]),
                $this->bCards('Pentru vizitatori și aparținători', [['Program și reguli de vizită', '', 'clock', 'reguli-si-program-de-vizita/'], ['Chestionar de feedback', '', 'chat', 'chestionar-de-feedback/']]),
                $this->bCards('Interes public', [['Informații de interes public', '', 'document', 'interes-public/'], ['Anunțuri și achiziții', '', 'cart', 'anunturi/'], ['Declarație privind accesibilitatea', '', 'a11y', 'declaratie-privind-accesibilitatea/']]),
            ]],
            ['internare-si-externare', 'Internare și externare', 'page', 'informatii-utile', 'Programarea internării', $this->html($L['admission']['intro']), [
                $this->bList('Programarea se poate face', $L['admission']['how']),
                $this->bCards('', [['Centrală – apoi tasta secției', $k['phone'], 'phone', 'tel:' . $k['phone_href']]]),
                $this->bList('Documente necesare la internare', $L['admission']['docs']),
                $this->bNotice(str_replace('ATENTIE !!!', 'ATENȚIE!', $L['admission']['warning'][0])),
                $this->bList('La externare pacientul va primi', $L['admission']['discharge_docs']),
                $this->bText('Informații despre externare', $this->html($L['admission']['discharge_text'])),
                $this->bList('Ce să aveți la internare', ['Pijama, halat, papuci de interior, obiecte și produse de igienă personală', 'Medicamentele pentru tratamentul afecțiunilor cronice, unde este cazul (diabetici etc.)']),
            ], false, 'Pentru pacienți'],
            ['servicii-decontate-prin-cas', 'Servicii decontate prin CASMB', 'page', 'informatii-utile', 'Servicii medicale gratuite, decontate prin CASMB', $this->html(['Ca pacient asigurat, ai acces gratuit la consultații, analize și investigații decontate de Casa de Asigurări de Sănătate a Municipiului București, pe baza biletului de trimitere și în limita fondurilor contractate.']), [
                $this->bDocs('', [['Servicii pentru asigurați – CASMB', 'https://www.casmb.ro/asigurati_servicii.php'], ['Investigații paraclinice decontate de CASMB', 'http://www.cnas.ro/casmb/page/investigatii-paraclinice-decontate-de-casmb.html']]),
                $this->bCards('Ce beneficii ai la noi?', [['Medici cu experiență', '', 'people', ''], ['Tehnologie medicală modernă', '', 'cpu', ''], ['Laborator acreditat RENAR', '', 'flask', ''], ['Ambulatoriu integrat', '', 'stethoscope', '']]),
                $this->bList('De ce documente ai nevoie?', ['Bilet de trimitere de la medicul de familie sau de la un medic specialist aflat în contract cu CASMB', 'Cardul de sănătate', 'Dovada calității de asigurat (sau adeverință eliberată de CASMB, în lipsa cardului)', 'CI / BI / Pașaport / Certificat de naștere, original și xerocopie']),
                $this->bText('', '<p>În lipsa biletului de trimitere, serviciile pot fi oferite contra cost, conform <a href="{siteUrl}servicii-medicale-cu-plata/">listei de tarife</a>.</p>'),
                $this->bCards('Servicii decontate', [['Ambulatoriu de specialitate', '', 'stethoscope', 'ambulatoriu/'], ['Laborator analize medicale', '', 'flask', 'service/laborator/'], ['Radiologie și imagistică', '', 'xray', 'service/radiologie/'], ['Medicină fizică și reabilitare', '', 'run', 'service/recuperare/']]),
            ]],
            ['servicii-medicale-cu-plata', 'Tarife servicii medicale', 'pricesPage', 'informatii-utile', 'Tarife servicii medicale', $this->html([$L['price_note'][1]]), [
                $this->bNotice($L['price_note'][0]),
            ]],
            ['drepturile-pacientilor', 'Drepturile și obligațiile pacienților', 'page', 'informatii-utile', 'Drepturile pacienților', $this->html(array_slice($L['rights']['intro'], 0, 1)), array_merge(
                array_map(fn($g) => $this->bList($g['title'], $g['items']), $L['rights']['groups']),
                [$this->bList('Obligațiile pacienților', $L['rights']['obligations'])],
            )],
            ['program-garzi', 'Program gărzi spital', 'page', 'informatii-utile', 'Programul gărzilor din spital', $this->html(['Spitalul asigură asistență medicală 24/24 h, 7/7 zile, cu linii de gardă pentru obstetrică-ginecologie, neonatologie, diabet, nutriție și boli metabolice, medicină internă, chirurgie generală, ATI și laborator de analize medicale.']), [
                $this->bDocs('', array_map(fn($g) => [$g['title'], $g['url']], $L['garzi'])),
                $this->bCards('', [['Camera de gardă', $k['phone'] . ' – tasta 1', 'ambulance', 'tel:' . $k['phone_href']]]),
            ]],
            ['chestionar-de-feedback', 'Chestionar de feedback', 'page', 'informatii-utile', 'Spune-ne părerea ta și ajută-ne să fim mai buni!', $this->html(['Opinia pacienților și a aparținătorilor ne ajută să îmbunătățim calitatea serviciilor. Puteți completa chestionarul oficial de feedback al Ministerului Sănătății sau chestionarul de satisfacție pe care îl primiți la externare (se lasă în urna special amenajată în secție).']), [
                $this->bDocs('', [['Completează chestionarul online', $this->cfg['feedback_url']]]),
                $this->bText('', '<p>Sesizări privind integritatea: <a href="mailto:' . ($k['email_integrity'] ?? $k['email']) . '">' . ($k['email_integrity'] ?? $k['email']) . '</a></p>'),
            ]],
            ['intrebari-frecvente', 'Întrebări frecvente', 'page', 'informatii-utile', '', '', [
                $this->bAccordion('Răspunsuri la cele mai frecvente întrebări', array_map(fn($f) => [$f['q'], $f['a']], $L['faq'])),
            ]],
            ['reguli-si-program-de-vizita', 'Program și reguli de vizită', 'page', 'informatii-utile', '', '', [
                $this->bTable('Program de vizită pacienți', ['Secție', 'Program', ''], $this->cfg['visiting']),
                $this->bDocs('', [['Program de vizită aparținători (PDF)', $this->cfg['visiting_pdf']]]),
                $this->bList('Reguli pentru vizitatori', ['Vizitatorii respectă orele de vizită impuse de specificul fiecărei secții', 'La intrarea în secție, vizitatorii se echipează cu halate și papuci de protecție', 'Pacienții sunt rugați să limiteze pe cât posibil numărul vizitatorilor', 'Fumatul și consumul de băuturi alcoolice sunt interzise în incinta spitalului', 'Vizitatorii respectă regulile de acces, de conduită și disciplină ale spitalului']),
            ], false, 'Pentru vizitatori și aparținători'],
            ['interes-public', 'Interes public', 'publicInterest', 'informatii-utile', 'Solicitare informații de interes public', $this->html(['Solicitările de informații de interes public în baza Legii nr. 544/2001 se adresează secretariatului spitalului.']), [], false, 'Interes public'],
            ['anunturi', 'Anunțuri și achiziții', 'page', 'informatii-utile', '', '', [
                $this->bDocs('Anunțuri publicitare și achiziții', array_map(fn($a) => [$a['title'], $a['url']], $L['announcements'])),
                $this->bDocs('Planul anual al achizițiilor publice', array_slice(current(array_filter($L['public_interest'], fn($p) => $p['title'] === 'Achiziții publice'))['docs'], 0, 1)),
            ]],
            ['pentru-vizitatori-si-apartinatori', 'Pentru vizitatori și aparținători', 'page', 'informatii-utile', '', '', [
                $this->bCards('', [['Program și reguli de vizită', 'Programul de vizită pe secții și regulile pentru vizitatori.', 'clock', 'reguli-si-program-de-vizita/'], ['Chestionar de feedback', 'Spune-ne cum ți s-a părut experiența în spitalul nostru.', 'chat', 'chestionar-de-feedback/']]),
            ], true],
            ['educatie-pentru-sanatate', 'Campanii de sănătate', 'newsIndex', 'informatii-utile', '', '', [], true],
            ['contact', 'Contact', 'contactPage', null, '', '', [
                $this->bList('Centrala telefonică', ['Tasta 1 – Camera de gardă', 'Tasta 4 – Imagistică medicală (1 Radiologie, 2 CT, 3 Mamograf)', 'Tasta 5 – Secții spital (1 Obstetrică-Ginecologie, 2 Neonatologie, 3 Medicină internă, 4 Diabet, 5 Chirurgie, 6 Recuperare, 7 Alergologie, 8 Anatomie patologică, 9 ATI)', 'Tasta 6 – Laborator analize (1 Punct de recoltare)']),
            ]],
            ['confidentialitate', 'Confidențialitate', 'page', null, 'Protecția datelor cu caracter personal', $this->html([$this->cfg['legal_name'] . ' prelucrează datele cu caracter personal în conformitate cu Regulamentul (UE) 2016/679 (GDPR) și cu legislația națională aplicabilă.', '[Conținut de completat de către spital.]', 'Pentru exercitarea drepturilor privind datele personale vă puteți adresa la ' . $k['email'] . '.']), [], true],
            ['declaratie-privind-accesibilitatea', 'Declarație privind accesibilitatea', 'page', null, 'Angajamentul nostru privind accesibilitatea', $this->html([$this->cfg['legal_name'] . ' se angajează să asigure accesibilitatea website-ului său pentru toate persoanele, inclusiv pentru persoanele cu dizabilități, în conformitate cu legislația în vigoare și cu recomandările WCAG 2.1, nivel AA.']), [
                $this->bList('Accesibilitatea pe site', ['structură semantică a paginilor și navigare din tastatură', 'texte alternative pentru imagini', 'contrast adecvat între text și fundal', 'design responsive, adaptat pentru dispozitive mobile']),
                $this->bText('Activarea meniului pentru Accesibilitate', $this->html(['Apăsați butonul rotund din colțul stânga-jos al ecranului pentru a mări sau micșora textul, a activa contrastul ridicat, tonurile de gri sau sublinierea linkurilor.'])),
                $this->bText('Conținut neaccesibil', $this->html(['Unele documente PDF scanate pot să nu fie complet accesibile. Le puteți solicita într-un format alternativ folosind datele de contact de mai jos.'])),
                $this->bText('Date de contact pentru utilizatori', '<p>Email: <a href="mailto:' . $k['email'] . '">' . $k['email'] . '</a><br>Telefon: ' . $k['phone'] . '</p>'),
            ], true],
        ];

        $structures = Craft::$app->getStructures();
        $section = Craft::$app->getEntries()->getSectionByHandle('pages');
        foreach ($pages as $p) {
            [$slug, $title, $type, $parent, $heading, $intro, $blocks] = $p;
            $hide = $p[7] ?? false;
            $group = $p[8] ?? '';
            $entry = $this->upsert('pages', $type, $slug, $title, [
                'heading' => $heading, 'body' => $intro, 'contentBlocks' => $this->blocks($blocks),
                'hideFromNav' => $hide, 'navGroup' => $group,
            ]);
            // Keep the source order within each level of the structure.
            if ($parent) {
                $structures->append($section->structureId, $entry, Entry::find()->id($this->ids['pages'][$parent])->status(null)->one());
            } else {
                $structures->appendToRoot($section->structureId, $entry);
            }
        }
    }

    // ------------------------------------------------------------------ block builders

    private function bText(string $h, string $html): array { return ['blockText', ['heading' => $h, 'body' => $html]]; }
    private function bMedia(string $h, string $html, string $img): array { return ['blockMedia', ['heading' => $h, 'body' => $html, 'image' => $this->assetIds([$img])]]; }
    private function bList(string $h, array $items): array { return ['blockList', ['heading' => $h, 'listItems' => $this->rows(array_map(fn($x) => [$x], $items))]]; }
    private function bNotice(string $text): array { return ['blockNotice', ['note' => $text]]; }
    private function bAccordion(string $h, array $items): array { return ['blockAccordion', ['heading' => $h, 'accordionItems' => $this->rows($items)]]; }
    private function bCards(string $h, array $items): array { return ['blockCards', ['heading' => $h, 'cardItems' => $this->rows($items)]]; }

    private function bTable(string $h, array $headings, array $rows): array
    {
        return ['blockTable', ['heading' => $h, 'tableHeadings' => implode(' | ', $headings), 'tableRows' => $this->rows($rows)]];
    }

    /** @param array<array{0:string,1:string}> $docs [title, url-or-uploads-path] */
    private function bDocs(string $h, array $docs): array
    {
        [$assets, $links] = $this->splitDocs($docs);
        return ['blockDocuments', ['heading' => $h, 'documents' => $assets, 'docLinks' => $this->rows($links)]];
    }

    /**
     * Local files (uploads/...) become related assets, keeping their titles; everything else becomes a link row.
     * @return array{0:int[],1:array}
     */
    private function splitDocs(array $docs): array
    {
        $assets = [];
        $links = [];
        foreach ($docs as [$title, $url]) {
            if (!$url) {
                continue;
            }
            if (str_starts_with($url, 'uploads/') && ($asset = $this->asset($url))) {
                if ($asset->title !== $title) {
                    $asset->title = $title;
                    Craft::$app->getElements()->saveElement($asset);
                }
                $assets[] = $asset->id;
            } else {
                $links[] = [$title, $url];
            }
        }
        return [$assets, $links];
    }

    private function blocks(array $blocks): array
    {
        $out = [];
        foreach (array_values($blocks) as $i => [$type, $fields]) {
            $out['new' . ($i + 1)] = ['type' => $type, 'enabled' => true, 'fields' => $fields];
        }
        return $out;
    }

    // ------------------------------------------------------------------ helpers

    private function html(array $paras): string
    {
        return implode('', array_map(fn($p) => '<p>' . htmlspecialchars($p, ENT_QUOTES) . '</p>', array_filter($paras)));
    }

    /** Table field rows: list of positional arrays -> [['col1' => …, 'col2' => …], …] */
    private function rows(array $rows): array
    {
        return array_map(function($r) {
            $out = [];
            foreach (array_values((array)$r) as $i => $v) {
                $out['col' . ($i + 1)] = $v;
            }
            return $out;
        }, array_values($rows));
    }

    private function asset(?string $path): ?Asset
    {
        if (!$path || !str_starts_with($path, 'uploads/')) {
            return null;
        }
        $rel = substr($path, strlen('uploads/'));
        $dir = dirname($rel);
        return Asset::find()->volume('uploads')->folderPath($dir === '.' ? '' : $dir . '/')->filename(basename($rel))->one();
    }

    /** @return int[] */
    private function assetIds(array $paths): array
    {
        $ids = [];
        foreach ($paths as $p) {
            if ($a = $this->asset($p)) {
                $ids[] = $a->id;
            } elseif ($p) {
                $this->stderr("  missing asset: $p\n");
            }
        }
        return $ids;
    }

    private function upsert(string $section, string $type, string $slug, string $title, array $fields, ?callable $tweak = null): Entry
    {
        $entry = Entry::find()->section($section)->slug($slug)->status(null)->one();
        if (!$entry) {
            $entry = new Entry();
            $entry->sectionId = Craft::$app->getEntries()->getSectionByHandle($section)->id;
            $entry->slug = $slug;
        }
        $entry->setTypeId(Craft::$app->getEntries()->getEntryTypeByHandle($type)->id);
        $entry->title = $title;
        $entry->setFieldValues($fields);
        if ($tweak) {
            $tweak($entry);
        }
        $this->save($entry, "$section/$slug");
        return Entry::find()->id($this->ids[$section][$slug] = $entry->id)->status(null)->one();
    }

    private function save($element, string $label): void
    {
        if (!Craft::$app->getElements()->saveElement($element)) {
            throw new \RuntimeException("Could not save $label: " . Json::encode($element->getErrors()));
        }
        $this->stdout("  saved $label\n");
    }
}
