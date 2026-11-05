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
 *     php craft malaxa/import                # then: globals, prices, hospital, ambulatory, doctors, news, pages, documents
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
        $hospital = Json::decode(file_get_contents("$src/content/hospital.json"));
        $ambulatory = Json::decode(file_get_contents("$src/content/ambulatory.json"));
        $docs = Json::decode(file_get_contents("$src/content/doctors.json"));
        $news = Json::decode(file_get_contents("$src/content/news.json"));

        $this->importGlobals();
        $this->importPriceGroups();
        $this->importUnits('hospital', 'hospitalUnit', $hospital);
        $this->importUnits('ambulatory', 'cabinet', $ambulatory);
        $this->linkUnits($hospital, $ambulatory);
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
            'contentUpdated' => $c['content_updated'] ?? '',
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

    /** Hospital structures and outpatient cabinets share one shape (content/hospital.json, content/ambulatory.json). */
    private function importUnits(string $section, string $type, array $items): void
    {
        foreach ($items as $s) {
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
            $priceGroupId = $this->ids['priceGroups'][StringHelper::slugify($s['price_group'] ?? '')] ?? null;
            $fields = [
                'iconName' => $s['icon'], 'summary' => $s['summary'], 'beds' => $s['beds'] ?? '',
                'body' => $this->linesHtml($s['intro'] ?: [$s['summary']]),
                'contentBlocks' => $this->blocks($blocks),
                'equipment' => $this->rows(array_map(fn($x) => [ucfirst($x)], $s['equipment'] ?? [])),
                'gallery' => $this->assetIds($s['gallery'] ?? []),
                'pending' => !empty($s['pending']),
                'hours' => $this->rows(array_map(fn($x) => [$x], $s['hours'] ?? [])),
                'schedule' => $this->rows($s['schedule'] ?? []),
                'phones' => $this->rows(array_map(fn($x) => [$x], $s['phone'] ?? [])),
                'docLinks' => $this->rows($s['links'] ?? []),
                'priceGroup' => $priceGroupId ? [$priceGroupId] : [],
            ];
            if ($section === 'hospital') {
                $fields['unitCategory'] = $s['category'];
            }
            $this->upsert($section, $type, $s['slug'], $s['name'], $fields);
        }
    }

    /** "Vezi și": each section points to its cabinet and each cabinet to its section. */
    private function linkUnits(array $hospital, array $ambulatory): void
    {
        foreach ([['hospital', $hospital, 'cabinet', 'ambulatory'], ['ambulatory', $ambulatory, 'structure', 'hospital']] as [$sec, $items, $key, $other]) {
            foreach ($items as $s) {
                $target = $this->ids[$other][$s[$key] ?? ''] ?? null;
                $e = Entry::find()->id($this->ids[$sec][$s['slug']])->status(null)->one();
                $e->setFieldValue('relatedUnit', $target ? [$target] : []);
                $this->save($e, "$sec/{$s['slug']} (link)");
            }
        }
    }

    private function importDoctors(array $docs): void
    {
        // Alphabetical by surname, then first name (titles ignored) – the order used on every list.
        $key = fn($n) => preg_replace('/\p{Mn}/u', '', \Normalizer::normalize(mb_strtolower(preg_replace('/^(Dr\.|Biol\.|Psiholog)\s*/u', '', $n)), \Normalizer::FORM_D));
        usort($docs, fn($a, $b) => strcmp($key($a['name']), $key($b['name'])));
        $structures = Craft::$app->getStructures();
        $section = Craft::$app->getEntries()->getSectionByHandle('doctors');
        foreach ($docs as $d) {
            $e = $this->upsert('doctors', 'doctor', $d['slug'], $d['name'], [
                'hospitalUnit' => isset($d['section']) && isset($this->ids['hospital'][$d['section']]) ? [$this->ids['hospital'][$d['section']]] : [],
                'cabinet' => isset($d['cabinet']) && isset($this->ids['ambulatory'][$d['cabinet']]) ? [$this->ids['ambulatory'][$d['cabinet']]] : [],
                'grade' => $d['grade'] ?? '', 'role' => $d['role'] ?? '', 'bio' => $d['bio'] ?? '',
                'photo' => $this->assetIds([$d['photo'] ?? null]),
            ]);
            $structures->appendToRoot($section->structureId, $e);
        }
        // Doctors no longer in the list (or renamed) are removed.
        $keep = array_column($docs, 'slug');
        foreach (Entry::find()->section('doctors')->status(null)->all() as $e) {
            if (!in_array($e->slug, $keep, true)) {
                Craft::$app->getElements()->deleteElement($e, true);
                $this->stdout("  removed doctors/{$e->slug}\n");
            }
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
        foreach ($this->lists['public_interest'] as $p) {
            [$assets, $links] = $this->splitDocs($p['docs'] ?? []);
            $linked = isset($p['page']) ? ($this->ids['pages'][rtrim($p['page'], '/')] ?? null) : null;
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
            'body' => '<p>Înființat în 1963 ca policlinică a platformei industriale „23 August”, spitalul poartă din 1991 numele industriașului Nicolae Malaxa. Astăzi are 263 de paturi pentru spitalizare continuă și 10 pentru spitalizare de zi, secții clinice universitare, cabinete de specialitate în ambulatoriu și camera de gardă non-stop.</p>',
            'image' => $this->assetIds([$this->cfg['hero_image'] ?? null]),
            'cardItems' => $this->rows([
                ['Spital acreditat', 'Acreditat ANMCS, certificat ISO 9001, laborator acreditat RENAR (ISO 15189).', 'award', ''],
                ['Clinici universitare', 'Secții clinice în colaborare cu UMF „Carol Davila”, cu activitate de cercetare și studii clinice.', 'people', ''],
                ['Gardă non-stop', 'Linii de gardă 24/24 h pentru obstetrică-ginecologie, neonatologie, diabet, medicină internă, chirurgie generală, ATI și laborator.', 'ambulance', ''],
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

        $o = $L['organigram'];
        $pay = $L['payment'];
        $K = $L['contracts'];
        $prog = current(array_filter($L['public_interest'], fn($x) => $x['title'] === 'Programe naționale'))['docs'] ?? [];
        $info = fn(array $items) => array_map(fn($i) => [$i[0], '', $i[2], $i[1]], $items);

        // [slug, title, type, parent slug, heading, intro html, blocks, hideFromNav, navGroup, extra fields]
        $pages = [
            ['despre-noi', 'Despre noi', 'page', null, 'Scurt istoric', '', [
                $this->bMedia('Scurt istoric', $this->html([$L['history'][0]]), 'uploads/images/nicolae-malaxa.jpg'),
                $this->bMedia('', $this->html([$L['history'][1]]), 'uploads/images/locomotiva.jpg'),
                $this->anchor($this->bCards('', [['Misiune', $L['mission'], 'hands', ''], ['Viziune', $L['vision'], 'star', '']]), 'misiune'),
                $this->bCards('Valori', array_map(fn($v, $i) => [$v['title'], $v['text'], $i, ''], $L['values'], ['hands', 'award', 'cpu', 'check'])),
            ]],
            ['misiune-viziune-valori', 'Misiune, viziune, valori', 'page', 'despre-noi', '', '', [], false, '', ['linkUrl' => 'despre-noi/#misiune']],
            ['conducere', 'Conducere', 'page', 'despre-noi', '', '', [
                $this->anchor($this->bCards('Conducerea', array_map(fn($m) => [$m['name'], $m['role'] . (isset($m['audiente']) ? "\nAudiențe: " . $m['audiente'] : ''), 'user', ''], $L['management'])), 'conducerea'),
                $this->anchor($this->bTable('Consiliul de administrație (CA)', ['Calitate', 'Nume', 'Reprezentant al'], array_map(fn($b) => [$b['rank'], $b['name'], $b['represents'] ?? ''], $L['board'])), 'ca'),
                $this->bDocs('', [$L['board_doc']]),
                $this->anchor($this->bTable('Comitetul director (CD)', ['Funcție', 'Nume'], array_map(fn($m) => [$m['role'], $m['name']], $L['management'])), 'cd'),
                $this->anchor($this->bTable('Consiliul etic (CE)', ['Calitate', 'Nume'], array_map(fn($b) => [$b['rank'], $b['name'] . (!empty($b['represents']) ? ' – ' . $b['represents'] : '')], $L['ethics'])), 'ce'),
                $this->bDocs('', [['Anuarul consiliului etic – 2020', 'uploads/docs/files/Anuarul Etic-2020.pdf'], ['Raportul consiliului etic – semestrul II 2020', 'uploads/docs/files/Raport Consiliul Etic-s2.2020.pdf']]),
                $this->bText('', '<p>Sesizări privind integritatea: <a href="mailto:' . ($k['email_integrity'] ?? $k['email']) . '">' . ($k['email_integrity'] ?? $k['email']) . '</a></p>'),
            ], false, '', ['showToc' => true]],
            ['structura-organizatorica', 'Structura organizatorică', 'page', 'despre-noi', '', '', [
                $this->bText('', $this->html(['Structura de mai jos este cea din organigrama aprobată de Administrația Spitalelor și Serviciilor Medicale București (ASSMB). „Posturi” reprezintă numărul de posturi aprobate (conducere + execuție).'])),
                $this->bDocs('', [$o['source']]),
                $this->bList('Conducere', $o['leadership']),
                $this->bTable('Secții și compartimente clinice', ['Paturi', 'Secție / compartiment', 'Posturi'], $o['clinic']),
                $this->bText('', '<p><strong>Total:</strong> ' . htmlspecialchars($o['beds_total']) . '.</p>'),
                $this->bTable('Laboratoare, explorări paraclinice și alte structuri medicale', ['Structură', 'Posturi'], $o['paraclinic']),
                $this->bTable('Ambulatoriu – cabinete de specialitate', ['Cabinet', 'Posturi'], $o['ambulatory']),
                $this->bTable('Structuri funcționale și administrative', ['Structură', 'Posturi'], $o['support']),
                $this->bText('', '<p><strong>Total posturi:</strong> ' . htmlspecialchars($o['posts_total']) . '.</p>'),
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
            ['spital', 'Spital', 'hospitalIndex', null, 'Structurile spitalului', '<p>Internarea continuă și de zi, camera de gardă, laboratoarele și serviciile paraclinice. Pentru consultații fără internare, vedeți <a href="{siteUrl}ambulatoriu/">cabinetele din ambulatoriu</a>.</p>', []],
            ['centre-de-excelenta', 'Centre de excelență', 'page', 'spital', '', '', [
                $this->bCards('', [
                    ['Centrul de Diabet, Nutriție și Boli Metabolice', 'Secție clinică cu 45 de paturi, spitalizare de zi și cabinete de ambulatoriu cu program zilnic; derulează Programul Național de Sănătate – Diabet.', 'drop', 'service/diabet/'],
                    ['Clinica universitară de Alergologie și Imunologie', 'Clinică universitară a UMF „Carol Davila”, cu laborator de imunologie clinică și testare alergologică in vivo și in vitro.', 'flask', 'service/alergologie/'],
                    ['Laboratorul de analize medicale acreditat RENAR', 'Acreditat conform ISO 15189:2013 pentru hematologie, chimie clinică, imunologie și parazitologie.', 'microscope', 'service/laborator/'],
                    ['Secția Clinică Obstetrică-Ginecologie', '50 de paturi, 2 săli de naștere, laparoscopie STORZ și nucleu de cercetare cu studii clinice în desfășurare.', 'female', 'service/obstetrica-ginecologie/'],
                ]),
            ], true],
            ['ambulatoriu', 'Ambulatoriu', 'ambulatoryIndex', null, 'Servicii medicale în ambulatoriu', '<p>Consultații de specialitate fără internare. Pentru internare și camera de gardă, vedeți <a href="{siteUrl}spital/">structurile spitalului</a>.</p>', []],
            ['team', 'Medici', 'doctorsIndex', null, '', $this->html(['Medicii sunt prezentați în ordinea alfabetică a numelui, urmat de prenume. Sub fiecare nume sunt trecute secția din spital și/sau cabinetul din ambulatoriu.']), []],
            ['informatii-utile', 'Informații utile', 'page', null, '', '', [
                $this->bCards('Pentru pacienți', $info([
                    ['Tipuri de prezentare', 'tipuri-de-prezentare/', 'clipboard'], ['Servicii decontate prin CASMB', 'servicii-decontate-prin-cas/', 'check'],
                    ['Contracte cu CASMB și CNAS', 'contracte-casmb-cnas/', 'contract'], ['Plata serviciilor medicale', 'servicii-medicale-cu-plata/', 'money'],
                    ['Drepturile și obligațiile pacienților', 'drepturile-pacientilor/', 'shield'], ['Program gărzi spital', 'program-garzi/', 'ambulance'],
                    ['Campanii de sănătate', 'educatie-pentru-sanatate/', 'award'], ['Chestionar de feedback', 'chestionar-de-feedback/', 'chat'],
                    ['Întrebări frecvente', 'intrebari-frecvente/', 'clipboard'],
                ])),
                $this->bCards('Pentru vizitatori și aparținători', $info([['Program de vizită', 'reguli-si-program-de-vizita/', 'clock'], ['Chestionar de feedback', 'chestionar-de-feedback/', 'chat']])),
                $this->bCards('Interes public', $info([['Informații de interes public', 'interes-public/', 'document'], ['Anunțuri și achiziții', 'anunturi/', 'cart'], ['Declarație privind accesibilitatea', 'declaratie-privind-accesibilitatea/', 'a11y']])),
            ]],
            ['tipuri-de-prezentare', 'Tipuri de prezentare', 'presentationPage', 'informatii-utile', '', $this->html(['Alegeți modul în care vă prezentați la spital. Pentru fiecare găsiți specificațiile, timpul alocat, modalitățile, condițiile, documentele necesare și excepțiile.']),
                array_map(fn($t) => $this->anchor(['blockPresentation', ['heading' => $t['title'], 'iconName' => $t['icon'], 'presentationRows' => $this->rows(array_map(fn($f) => [$f[0], implode("\n", $f[1])], $t['fields']))]], $t['id']), $L['presentation']),
                false, 'Pentru pacienți'],
            ['servicii-decontate-prin-cas', 'Servicii decontate prin CASMB', 'page', 'informatii-utile', 'Servicii medicale gratuite, decontate prin CASMB', $this->html(['Ca pacient asigurat, ai acces gratuit la consultații, analize și investigații decontate de Casa de Asigurări de Sănătate a Municipiului București, pe baza biletului de trimitere și în limita fondurilor contractate.']), [
                $this->bDocs('', [['Servicii pentru asigurați – CASMB', 'https://www.casmb.ro/asigurati_servicii.php'], ['Investigații paraclinice decontate de CASMB', 'http://www.cnas.ro/casmb/page/investigatii-paraclinice-decontate-de-casmb.html']]),
                $this->bCards('Ce beneficii ai la ' . $this->cfg['name'] . '?', [['Medici cu experiență', '', 'people', ''], ['Tehnologie medicală modernă', '', 'cpu', ''], ['Laborator acreditat RENAR', '', 'flask', ''], ['Cabinete de specialitate în ambulatoriu', '', 'stethoscope', '']]),
                $this->bList('De ce documente ai nevoie?', ['Bilet de trimitere de la medicul de familie sau de la un medic specialist aflat în contract cu CASMB', 'Cardul de sănătate', 'Dovada calității de asigurat (sau adeverință eliberată de CASMB, în lipsa cardului)', 'CI / BI / Pașaport / Certificat de naștere, original și xerocopie']),
                $this->bText('', '<p>În lipsa biletului de trimitere, serviciile pot fi oferite contra cost, conform <a href="{siteUrl}servicii-medicale-cu-plata/">listei de tarife</a>.</p>'),
                $this->bCards('', [['Ambulatoriu de specialitate', '', 'stethoscope', 'ambulatoriu/'], ['Laborator analize medicale', '', 'flask', 'service/laborator/'], ['Radiologie și imagistică', '', 'xray', 'service/radiologie/'], ['Medicină fizică și reabilitare', '', 'run', 'service/recuperare/']]),
            ]],
            ['contracte-casmb-cnas', 'Contracte cu CASMB și CNAS', 'page', 'informatii-utile', 'Contracte cu CASMB și CNAS', $this->html([$K['intro']]), [
                $this->bTable('', ['Tip', 'Descriere'], $K['types']),
                $this->bDocs('Documente', $prog),
                $this->bDocs('', [['CASMB – servicii pentru asigurați', 'https://www.casmb.ro/asigurati_servicii.php']]),
            ]],
            ['servicii-medicale-cu-plata', 'Plata serviciilor medicale', 'pricesPage', 'informatii-utile', 'Plata serviciilor medicale',
                '<p>Pacienții asigurați beneficiază de serviciile decontate de CASMB, pe baza biletului de trimitere (<a href="{siteUrl}servicii-decontate-prin-cas/">servicii decontate prin CASMB</a>). Serviciile se plătesc în următoarele situații:</p>'
                . $this->linesHtml($pay['when'])
                . '<h3>Tarife aprobate</h3><p>' . htmlspecialchars($pay['decision']) . '</p>'
                . '<h3>Alte situații în care se plătește</h3>' . $this->linesHtml($pay['other'])
                . '<h3>Cum se plătește</h3>' . $this->linesHtml(array_map(fn($x) => '– ' . $x, $pay['how'])), []],
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
            ['reguli-si-program-de-vizita', 'Program de vizită', 'page', 'informatii-utile', '', '', [
                $this->bTable('Program de vizită', ['Secție', 'Program', ''], $this->cfg['visiting']),
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
            ['confidentialitate', 'Confidențialitate', 'page', null, 'Protecția datelor cu caracter personal', $this->html([$this->cfg['legal_name'] . ' prelucrează datele cu caracter personal în conformitate cu Regulamentul (UE) 2016/679 (GDPR) și cu legislația națională aplicabilă.', '[[Conținut de completat de către spital.]]', 'Pentru exercitarea drepturilor privind datele personale vă puteți adresa la ' . $k['email'] . '.']), [], true],
            ['declaratie-privind-accesibilitatea', 'Declarație privind accesibilitatea', 'page', null, 'Angajamentul nostru privind accesibilitatea', $this->html([$this->cfg['legal_name'] . ' se angajează să asigure accesibilitatea website-ului său pentru toate persoanele, inclusiv pentru persoanele cu dizabilități, în conformitate cu legislația în vigoare și cu recomandările WCAG 2.1, nivel AA.']), [
                $this->bList('Accesibilitatea pe site', ['structură semantică a paginilor și navigare din tastatură', 'texte alternative pentru imagini', 'contrast adecvat între text și fundal', 'design responsive, adaptat pentru dispozitive mobile']),
                $this->bText('Activarea meniului pentru Accesibilitate', $this->html(['Apăsați butonul rotund din colțul stânga-jos al ecranului pentru a mări sau micșora textul, a activa contrastul ridicat, tonurile de gri sau sublinierea linkurilor.'])),
                $this->bText('Conținut neaccesibil', $this->html(['Unele documente PDF scanate pot să nu fie complet accesibile. Le puteți solicita într-un format alternativ folosind datele de contact de mai jos.'])),
                $this->bText('Date de contact pentru utilizatori', '<p>Email: <a href="mailto:' . $k['email'] . '">' . $k['email'] . '</a><br>Telefon: ' . $k['phone'] . '</p>'),
                $this->bText('Întocmirea declarației', $this->html(['Prezenta declarație a fost întocmită la data de ' . $this->roDate(new \DateTime()) . '.'])),
            ], true],
        ];

        // Pages replaced by this structure (their old URLs redirect, see config/redirects.php).
        foreach (['specialitati-medicale', 'echipa-de-management', 'internare-si-externare'] as $old) {
            if ($e = Entry::find()->section('pages')->slug($old)->status(null)->one()) {
                Craft::$app->getElements()->deleteElement($e, true);
                $this->stdout("  removed pages/$old\n");
            }
        }

        $structures = Craft::$app->getStructures();
        $section = Craft::$app->getEntries()->getSectionByHandle('pages');
        foreach ($pages as $p) {
            [$slug, $title, $type, $parent, $heading, $intro, $blocks] = $p;
            $entry = $this->upsert('pages', $type, $slug, $title, ($p[9] ?? []) + [
                'heading' => $heading, 'body' => $intro, 'contentBlocks' => $this->blocks($blocks),
                'hideFromNav' => $p[7] ?? false, 'navGroup' => $p[8] ?? '', 'showToc' => false, 'linkUrl' => '',
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

    /** Give a block an anchor (id), for links such as conducere/#ca. */
    private function anchor(array $block, string $id): array
    {
        $block[1]['anchor'] = $id;
        return $block;
    }

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

    private function roDate(\DateTime $d): string
    {
        $m = ['ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie', 'iulie', 'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie'];
        return $d->format('j') . ' ' . $m[(int)$d->format('n') - 1] . ' ' . $d->format('Y');
    }

    /** Lines as paragraphs; consecutive "– …" lines become a dashed list (like the static site). */
    private function linesHtml(array $lines): string
    {
        $out = '';
        $items = [];
        foreach (array_merge($lines, ['']) as $ln) {
            if (str_starts_with($ln, '– ')) {
                $items[] = '<li>' . htmlspecialchars(mb_substr($ln, 2), ENT_QUOTES) . '</li>';
                continue;
            }
            if ($items) {
                $out .= '<ul class="list-check">' . implode('', $items) . '</ul>';
                $items = [];
            }
            if ($ln !== '') {
                $out .= '<p>' . htmlspecialchars($ln, ENT_QUOTES) . '</p>';
            }
        }
        return $out;
    }

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
